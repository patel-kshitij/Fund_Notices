from typing import Any

import pandas as pd

from docs_check import REQUIRED_KEYS, read_frontmatter
from fund_notices.evaluate import RunResult, render, run_rows


def row(**changes: Any) -> dict[str, Any]:
    """One document's facts, as the evaluate run records them."""
    base: dict[str, Any] = {
        "doc_id": "test_001",
        "doc_type": "invoice",
        "untitled": False,
        "predicted": "invoice",
        "second_opinion": "invoice",
        "fields_right": 10,
        "fields": 10,
        "wrong_fields": "",
        "amounts_wrong": 0,
        "failed": False,
        "retried": False,
        "planted": "",
        "caught": False,
        "math_flag": False,
        "review": False,
        "reasons": "",
    }
    return base | changes


def result(rows: list[dict[str, Any]]) -> RunResult:
    return RunResult(
        pd.DataFrame(rows), model_calls=1, cache_hits=2, model_seconds=60.0, run_seconds=6.0
    )


ROWS = [
    row(
        doc_id="test_001",
        doc_type="capital_call",
        predicted="capital_call",
        second_opinion="capital_call",
        fields_right=14,
        fields=14,
        planted="split_total_mismatch",
        caught=True,
        math_flag=True,
        review=True,
        reasons="split_total: does not add up",
    ),
    row(
        doc_id="test_002",
        fields_right=9,
        wrong_fields="tax",
        amounts_wrong=1,
        math_flag=True,
        review=True,
    ),
    row(doc_id="test_003"),
]


def test_scores_count_catches_false_alarms_and_reviews() -> None:
    lines = dict(run_rows(result(ROWS)))
    assert lines["Fields right, all documents"] == "33/34 (97.1%)"
    assert lines["Documents with every field right"] == "2/3 (66.7%)"
    assert lines["Planted errors caught by the math checks"] == "1/1 (100.0%)"
    assert lines["Clean documents flagged by the math checks"] == "1/2 (50.0%)"
    assert lines["Documents sent to a person"] == "2/3 (66.7%)"
    assert lines["Model replies used"] == "3"
    assert lines["Amounts wrong, in money fields and line items"] == "1"


def test_results_page_passes_the_docs_check() -> None:
    page = render("fake", {"with": result(ROWS), "without": result(ROWS)})
    frontmatter = read_frontmatter(page)
    assert frontmatter is not None
    assert all(frontmatter.get(key) for key in REQUIRED_KEYS)
    assert "`test_002`" in page and "tax" in page
