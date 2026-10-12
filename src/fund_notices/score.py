"""Compare extracted fields with the answer file, one field at a time."""

from fund_notices.schema import ExtractedFields


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
