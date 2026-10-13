"""Plain helpers for the demo page in app.py. No Streamlit code, so tests can call them."""

from datetime import date
from decimal import Decimal
from typing import Any

from fund_notices.schema import AnswerFile, ExtractedFields, LineItem
from fund_notices.score import field_matches

NOT_SHOWN = "(not shown)"


def show(value: Any) -> str:
    """A value as text for the page. Money keeps every digit, with commas for reading."""
    if value is None:
        return NOT_SHOWN
    if isinstance(value, Decimal):
        return f"{value:,}"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return "; ".join(show_line(item) for item in value) or NOT_SHOWN
    return str(value)


def show_line(item: LineItem) -> str:
    return (
        f"{item.description}: {show(item.quantity)} x {show(item.unit_price)} = {show(item.amount)}"
    )


def field_rows(found: ExtractedFields, truth: ExtractedFields | None) -> list[dict[str, str]]:
    """One row per field: what the tool found, and, when the truth is known, whether it matches."""
    model = type(truth) if truth is not None else type(found)
    matches = field_matches(truth, found) if truth is not None else {}
    rows = []
    for name in model.model_fields:
        row = {"Field": name, "Found": show(getattr(found, name, None))}
        if truth is not None:
            row["Answer file"] = show(getattr(truth, name))
            row["Match"] = "yes" if matches[name] else "NO"
        rows.append(row)
    return rows


def choice_label(answer: AnswerFile) -> str:
    """How a test document is listed. Planted errors are marked, so a demo can show one caught."""
    return f"{answer.doc_id} (planted error)" if answer.planted_error else answer.doc_id


def without_frontmatter(text: str) -> str:
    """A docs page without its frontmatter block, ready to show."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + len("\n---\n") :]
    return text
