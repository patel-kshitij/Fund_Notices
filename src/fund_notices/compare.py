"""Compare Ollama models on a few train documents, to choose one.

Run with: python -m fund_notices.compare qwen3:4b llama3.2:3b

Only train documents are used, so the test set stays unseen. Replies are cached,
so a second run of the same model makes no model calls.
"""

import argparse
import time
from pathlib import Path

from fund_notices.extract import extract
from fund_notices.llm import CachedClient, OllamaClient
from fund_notices.pdftext import pdf_text
from fund_notices.schema import AnswerFile, DocType
from fund_notices.score import field_matches

ROOT = Path(__file__).resolve().parents[2]


def pick_documents(folder: Path, per_type: int) -> list[AnswerFile]:
    """The first per_type documents of each type, in file name order."""
    answers = [
        AnswerFile.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(folder.glob("*.json"))
    ]
    return [a for t in DocType for a in [a for a in answers if a.doc_type == t][:per_type]]


def run_model(model: str, answers: list[AnswerFile], folder: Path) -> str:
    """Extract every document with one model and return one line of results."""
    client = CachedClient(OllamaClient(model), ROOT / "cache")
    right = total = whole_docs = failed = 0
    start = time.perf_counter()
    for answer in answers:
        text = pdf_text(folder / f"{answer.doc_id}.pdf")
        result = extract(text, answer.doc_type, client)
        matches = field_matches(answer.fields, result.fields)
        right += sum(matches.values())
        total += len(matches)
        whole_docs += all(matches.values())
        failed += result.fields is None
    seconds = time.perf_counter() - start
    return (
        f"{model}: fields right {right}/{total}, "
        f"documents fully right {whole_docs}/{len(answers)}, "
        f"failed extractions {failed}, model calls {client.model_calls}, "
        f"cache hits {client.cache_hits}, run time {seconds:.1f} s"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="+", help="Ollama model names")
    parser.add_argument("--per-type", type=int, default=2, help="documents of each type")
    args = parser.parse_args()
    folder = ROOT / "data" / "train"
    answers = pick_documents(folder, args.per_type)
    if not answers:
        raise SystemExit("No train documents. Run: python -m fund_notices.generate")
    for model in args.models:
        print(run_model(model, answers, folder))


if __name__ == "__main__":
    main()
