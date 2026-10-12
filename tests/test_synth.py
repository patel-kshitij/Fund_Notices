from collections import Counter
from decimal import Decimal

from fund_notices.schema import (
    AnswerFile,
    CapitalCallNotice,
    DistributionNotice,
    DocType,
    ExtractedFields,
    Invoice,
)
from fund_notices.synth import build_dataset, shift_field

Dataset = tuple[list[AnswerFile], list[AnswerFile]]


def math_problems(fields: ExtractedFields) -> list[str]:
    """A small independent copy of the math rules, used only to test the generator."""
    problems = []
    if isinstance(fields, CapitalCallNotice):
        split = [fields.investments, fields.management_fee, fields.partnership_expenses]
    elif isinstance(fields, DistributionNotice):
        split = [fields.return_of_capital, fields.realized_gain, fields.income]
    else:
        for item in fields.line_items:
            assert item.quantity is not None and item.unit_price is not None
            if item.quantity * item.unit_price != item.amount:
                problems.append("line item")
        lines = sum((i.amount for i in fields.line_items if i.amount is not None), Decimal(0))
        if lines != fields.subtotal:
            problems.append("subtotal")
        assert fields.subtotal is not None and fields.tax is not None
        if fields.subtotal + fields.tax != fields.total:
            problems.append("total")
        return problems

    assert all(v is not None for v in split)
    if sum(v for v in split if v is not None) != fields.total_amount:
        problems.append("split")
    before, after = fields.unfunded_commitment_before, fields.unfunded_commitment_after
    assert before is not None and fields.total_amount is not None
    expected_after = (
        before - fields.total_amount if isinstance(fields, CapitalCallNotice) else before
    )
    if after != expected_after:
        problems.append("unfunded")
    return problems


def test_shift_field_moves_one_field_and_keeps_the_original() -> None:
    original = CapitalCallNotice(total_amount=Decimal("100.00"), management_fee=Decimal("5.00"))
    moved = shift_field(original, "total_amount", Decimal("1000.00"))
    assert moved.total_amount == Decimal("1100.00")
    assert moved.management_fee == Decimal("5.00")
    assert original.total_amount == Decimal("100.00")


def test_split_sizes_and_type_balance(dataset: Dataset) -> None:
    train, test = dataset
    assert Counter(a.doc_type for a in train) == {t: 14 for t in DocType}
    assert Counter(a.doc_type for a in test) == {t: 15 for t in DocType}


def test_planted_errors_only_in_test_notices(dataset: Dataset) -> None:
    train, test = dataset
    assert all(a.planted_error is None for a in train)
    flawed = [a for a in test if a.planted_error is not None]
    assert Counter(a.doc_type for a in flawed) == {
        DocType.CAPITAL_CALL: 3,
        DocType.DISTRIBUTION: 3,
    }


def test_clean_documents_add_up(dataset: Dataset) -> None:
    for answer in [*dataset[0], *dataset[1]]:
        if answer.planted_error is None:
            assert math_problems(answer.fields) == [], answer.doc_id


def test_planted_document_breaks_one_rule_and_records_the_truth(dataset: Dataset) -> None:
    for answer in dataset[1]:
        error = answer.planted_error
        if error is None:
            continue
        assert error.printed_value != error.correct_value
        # The answer file holds what the document prints, per decision 4.
        assert getattr(answer.fields, error.field) == error.printed_value
        assert len(math_problems(answer.fields)) >= 1
        repaired = answer.fields.model_copy(update={error.field: error.correct_value})
        assert math_problems(repaired) == [], answer.doc_id


def test_dates_and_currency_are_sane_in_every_document(dataset: Dataset) -> None:
    for answer in [*dataset[0], *dataset[1]]:
        f = answer.fields
        assert f.issue_date is not None and f.due_date is not None
        assert f.due_date >= f.issue_date
        assert f.currency is not None and len(f.currency) == 3


def test_same_seed_gives_same_dataset(dataset: Dataset) -> None:
    assert build_dataset() == dataset
    assert build_dataset(seed=1) != dataset


def test_every_type_has_untitled_documents_in_test(dataset: Dataset) -> None:
    untitled = Counter(a.doc_type for a in dataset[1] if a.title is None)
    assert all(untitled[t] >= 2 for t in DocType)


def test_ids_are_unique_and_never_reveal_the_type(dataset: Dataset) -> None:
    ids = [a.doc_id for a in [*dataset[0], *dataset[1]]]
    assert len(ids) == len(set(ids))
    assert not any(t.value in doc_id for t in DocType for doc_id in ids)


def test_invoices_have_line_items(dataset: Dataset) -> None:
    for answer in [*dataset[0], *dataset[1]]:
        if isinstance(answer.fields, Invoice):
            assert answer.fields.line_items
