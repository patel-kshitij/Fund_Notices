"""Compare extracted fields with the answer file, one field at a time."""

from decimal import Decimal

from fund_notices.schema import ExtractedFields, Invoice


def field_matches(expected: ExtractedFields, got: ExtractedFields | None) -> dict[str, bool]:
    """For each field of the expected model, whether the extraction got it exactly right.

    Money compares as Decimal, so 100.5 and 100.50 match. Text must match after
    trimming spaces. Line items count as one field and must all match.
    A failed extraction (None) gets every field wrong.
    """
    result: dict[str, bool] = {}
    for name in type(expected).model_fields:
        want = getattr(expected, name)
        have = None if got is None else getattr(got, name, None)
        if isinstance(want, str) and isinstance(have, str):
            want, have = want.strip(), have.strip()
        result[name] = got is not None and want == have
    return result


def amounts_wrong(expected: ExtractedFields, got: ExtractedFields | None) -> int:
    """How many numbers the extraction got wrong: money fields and line item numbers.

    A wrong amount is the costly mistake, because it can make a correct notice
    fail the checks or a wrong one pass. A line that is missing or extra counts
    all 3 of its numbers as wrong.
    """
    wrong = 0
    for name in type(expected).model_fields:
        want = getattr(expected, name)
        have = None if got is None else getattr(got, name, None)
        if isinstance(want, Decimal) and want != have:
            wrong += 1
    if isinstance(expected, Invoice):
        lines = got.line_items if isinstance(got, Invoice) else []
        for want_line, have_line in zip(expected.line_items, lines, strict=False):
            for part in ("quantity", "unit_price", "amount"):
                wrong += getattr(want_line, part) != getattr(have_line, part)
        wrong += 3 * abs(len(expected.line_items) - len(lines))
    return wrong
