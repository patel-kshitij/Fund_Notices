from decimal import Decimal

from fund_notices.checks import check
from fund_notices.schema import AnswerFile, CapitalCallNotice, Invoice, LineItem

Dataset = tuple[list[AnswerFile], list[AnswerFile]]


def test_every_clean_document_passes(dataset: Dataset) -> None:
    for answer in [*dataset[0], *dataset[1]]:
        if answer.planted_error is None:
            assert check(answer.fields) == [], answer.doc_id


def test_every_planted_error_is_caught_by_the_right_check(dataset: Dataset) -> None:
    planted = [a for a in dataset[1] if a.planted_error is not None]
    assert len(planted) == 6
    expected_check = {
        "split_total_mismatch": "split_total",
        "unfunded_after_mismatch": "unfunded_after",
    }
    for answer in planted:
        assert answer.planted_error is not None
        # A wrong total on a capital call also breaks the unfunded rule, so more
        # than one check may fire. The check named for the mistake must be one of them.
        checks = {p.check for p in check(answer.fields)}
        assert expected_check[answer.planted_error.kind] in checks, answer.doc_id


def test_missing_number_is_a_problem_not_a_pass() -> None:
    fields = CapitalCallNotice(
        investments=Decimal(10), management_fee=Decimal(1), total_amount=Decimal(11)
    )
    problems = [p for p in check(fields) if p.check == "split_total"]
    assert len(problems) == 1 and "partnership_expenses" in problems[0].detail


def test_invoice_line_that_does_not_multiply_out_is_caught() -> None:
    fields = Invoice(
        line_items=[LineItem(quantity=Decimal(2), unit_price=Decimal(10), amount=Decimal(21))],
        subtotal=Decimal(21),
        tax=Decimal(0),
        total=Decimal(21),
    )
    assert [p.check for p in check(fields)] == ["line_amount"]
