"""Run the whole pipeline on the test set and write docs/results.md.

Run with: FUND_NOTICES_MODEL=qwen3:4b python -m fund_notices.evaluate

Every number in the README comes from the file this writes. The pipeline runs
twice. The first run shows each prompt a worked example, which is the design.
The second leaves the example out, to show what the example adds. Replies are
cached, so a rerun makes no model calls and still reports the time each reply
first took. The test set is never used for training or retrieval.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from fund_notices.checks import CHECK_FOR_ERROR
from fund_notices.classify import train_classifier
from fund_notices.llm import CachedClient, OllamaClient, model_from_env
from fund_notices.pipeline import NoticeReader, load_split
from fund_notices.retrieve import TrainPool, minilm_embedder
from fund_notices.schema import AnswerFile
from fund_notices.score import amounts_wrong, field_matches

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "results.md"


@dataclass
class RunResult:
    rows: pd.DataFrame
    model_calls: int
    cache_hits: int
    model_seconds: float
    run_seconds: float


def run(
    reader: NoticeReader, client: CachedClient, texts: list[str], answers: list[AnswerFile]
) -> RunResult:
    """Read every document and keep one row of facts per document."""
    rows = []
    start = time.perf_counter()
    for number, (text, answer) in enumerate(zip(texts, answers, strict=True), start=1):
        outcome = reader.read(text)
        matches = field_matches(answer.fields, outcome.extraction.fields)
        planted = answer.planted_error
        found = {problem.check for problem in outcome.problems}
        rows.append(
            {
                "doc_id": answer.doc_id,
                "doc_type": str(answer.doc_type),
                "untitled": answer.title is None,
                "predicted": str(outcome.prediction.doc_type),
                "second_opinion": str(outcome.second_opinion),
                "fields_right": sum(matches.values()),
                "fields": len(matches),
                "wrong_fields": ", ".join(name for name, ok in matches.items() if not ok),
                "amounts_wrong": amounts_wrong(answer.fields, outcome.extraction.fields),
                "failed": outcome.extraction.fields is None,
                "retried": outcome.extraction.attempts > 1,
                "planted": "" if planted is None else planted.kind,
                "caught": planted is not None and CHECK_FOR_ERROR[planted.kind] in found,
                "math_flag": bool(outcome.problems),
                "review": outcome.needs_review,
                "reasons": "; ".join(outcome.review_reasons),
            }
        )
        print(f"  {number}/{len(texts)} {answer.doc_id}", flush=True)
    return RunResult(
        rows=pd.DataFrame(rows),
        model_calls=client.model_calls,
        cache_hits=client.cache_hits,
        model_seconds=client.model_seconds,
        run_seconds=time.perf_counter() - start,
    )


def ratio(part: int, whole: int) -> str:
    """For example 44/45 (97.8%)."""
    return f"{part}/{whole} ({part / whole:.1%})" if whole else "0/0"


def classification_rows(rows: pd.DataFrame) -> list[tuple[str, str]]:
    right = rows["predicted"] == rows["doc_type"]
    untitled = rows["untitled"]
    second = rows["second_opinion"] == rows["doc_type"]
    disagree = rows["predicted"] != rows["second_opinion"]
    return [
        ("Type right, all documents", ratio(right.sum(), len(rows))),
        ("Type right, untitled documents", ratio(right[untitled].sum(), untitled.sum())),
        ("MiniLM nearest neighbour right", ratio(second.sum(), len(rows))),
        ("Classifier and nearest neighbour disagree", str(disagree.sum())),
    ]


def run_rows(result: RunResult) -> list[tuple[str, str]]:
    rows = result.rows
    clean = rows["planted"] == ""
    planted = ~clean
    lines = [
        ("Fields right, all documents", ratio(rows["fields_right"].sum(), rows["fields"].sum()))
    ]
    for doc_type, group in rows.groupby("doc_type"):
        lines.append(
            (f"Fields right, {doc_type}", ratio(group["fields_right"].sum(), group["fields"].sum()))
        )
    every_field = (rows["fields_right"] == rows["fields"]).sum()
    lines += [
        ("Documents with every field right", ratio(every_field, len(rows))),
        ("Amounts wrong, in money fields and line items", str(rows["amounts_wrong"].sum())),
        ("Failed extractions", str(rows["failed"].sum())),
        ("Documents that needed the retry", str(rows["retried"].sum())),
        (
            "Planted errors caught by the math checks",
            ratio(rows["caught"][planted].sum(), planted.sum()),
        ),
        (
            "Clean documents flagged by the math checks",
            ratio(rows["math_flag"][clean].sum(), clean.sum()),
        ),
        ("Documents sent to a person", ratio(rows["review"].sum(), len(rows))),
        ("Model replies used", str(result.model_calls + result.cache_hits)),
        ("New model calls in this run", str(result.model_calls)),
        ("Model time, minutes", f"{result.model_seconds / 60:.1f}"),
        ("Model time per document, seconds", f"{result.model_seconds / len(rows):.1f}"),
        ("Run time of this run, minutes", f"{result.run_seconds / 60:.1f}"),
    ]
    return lines


def table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def wrong_field_table(rows: pd.DataFrame) -> str:
    wrong = rows[rows["wrong_fields"] != ""]
    mistakes = [(f"`{r.doc_id}`", f"`{r.doc_type}`", r.wrong_fields) for r in wrong.itertuples()]
    return table(("Document", "True type", "Wrong fields"), mistakes) if mistakes else "None."


def render(model: str, results: dict[str, RunResult]) -> str:
    main, without = results["with"], results["without"]
    both = [
        (name, value, other)
        for (name, value), (_, other) in zip(run_rows(main), run_rows(without), strict=True)
    ]
    rows = main.rows
    review = rows[rows["review"]]
    sent = [
        (f"`{r.doc_id}`", f"`{r.doc_type}`", f"`{r.planted}`" if r.planted else "none", r.reasons)
        for r in review.itertuples()
    ]
    today = date.today().isoformat()
    return f"""---
type: results
purpose: Scores from the last evaluate run. Written by the evaluate command, never by hand.
owner: Kshitij
reviewed: {today}
---

# Results

Written by `python -m fund_notices.evaluate` on {today}. Model: `{model}`.
The test set has {len(rows)} documents. None of them was used for training or retrieval.

## Classification

{table(("Measure", "Result"), classification_rows(rows))}

## Extraction, checks, and review

The design shows the model a worked example: the most similar train document
of the predicted type, with its answer. The last column leaves the example out.

{table(("Measure", "With worked example", "Without"), both)}

## Documents sent to a person

From the run with a worked example.

{table(("Document", "True type", "Planted error", "Reasons"), sent) if sent else "None."}

## Documents with a field extracted wrong

From the run with a worked example.

{wrong_field_table(rows)}

From the run without a worked example.

{wrong_field_table(without.rows)}
"""


def main() -> None:
    model = model_from_env()
    train_texts, train_answers = load_split(ROOT / "data" / "train")
    test_texts, test_answers = load_split(ROOT / "data" / "test")
    if not train_answers or not test_answers:
        raise SystemExit("No data. Run: python -m fund_notices.generate")
    classifier = train_classifier(train_texts, train_answers)
    embed = minilm_embedder(ROOT / "cache" / "models")
    pool = TrainPool(train_texts, train_answers, classifier, embed)
    results = {}
    for name, use_examples in (("with", True), ("without", False)):
        print(f"Reading the test set {name} a worked example", flush=True)
        client = CachedClient(OllamaClient(model), ROOT / "cache")
        results[name] = run(
            NoticeReader(classifier, pool, client, use_examples), client, test_texts, test_answers
        )
    RESULTS.write_text(render(model, results), encoding="utf-8")
    print(f"Wrote {RESULTS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
