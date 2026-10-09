from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from fund_notices.schema import CapitalCallNotice, DistributionNotice, Invoice


def test_money_parses_to_exact_decimal() -> None:
    notice = CapitalCallNotice.model_validate({"total_amount": "1234567.89"})
    assert notice.total_amount == Decimal("1234567.89")
    assert isinstance(notice.total_amount, Decimal)


def test_cents_add_up_exactly() -> None:
    notice = CapitalCallNotice.model_validate(
        {"investments": "0.10", "management_fee": "0.20", "total_amount": "0.30"}
    )
    assert notice.investments is not None
    assert notice.management_fee is not None
    assert notice.investments + notice.management_fee == notice.total_amount


def test_missing_fields_become_none() -> None:
    notice = CapitalCallNotice.model_validate({"fund_name": "Harbor Ridge Partners III"})
    assert notice.due_date is None
    assert notice.total_amount is None


def test_wrong_document_still_parses() -> None:
    # The split does not add up, the due date is before the issue date, and the
    # currency is not 3 letters. The schema must accept all of it.
    notice = CapitalCallNotice.model_validate(
        {
            "issue_date": "2026-03-15",
            "due_date": "2026-03-01",
            "currency": "US",
            "investments": "100.00",
            "management_fee": "10.00",
            "partnership_expenses": "5.00",
            "total_amount": "999.00",
        }
    )
    assert notice.currency == "US"
    assert notice.due_date == date(2026, 3, 1)
    assert notice.total_amount == Decimal("999.00")


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CapitalCallNotice.model_validate({"total_amout": "100.00"})


@pytest.mark.parametrize(
    "field, value",
    [("total_amount", "a lot"), ("issue_date", "next Tuesday")],
)
def test_wrong_type_is_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        CapitalCallNotice.model_validate({field: value})


def test_json_round_trip_keeps_money_as_exact_string() -> None:
    notice = CapitalCallNotice.model_validate({"total_amount": "250000.10"})
    dumped = notice.model_dump(mode="json")
    assert dumped["total_amount"] == "250000.10"
    assert CapitalCallNotice.model_validate(dumped) == notice


def test_invoice_line_items_parse() -> None:
    invoice = Invoice.model_validate(
        {
            "invoice_number": "INV-0042",
            "line_items": [
                {
                    "description": "Audit fieldwork",
                    "quantity": "12",
                    "unit_price": "350.00",
                    "amount": "4200.00",
                }
            ],
            "subtotal": "4200.00",
        }
    )
    assert len(invoice.line_items) == 1
    assert invoice.line_items[0].amount == Decimal("4200.00")


def test_invoice_without_line_items_gets_an_empty_list() -> None:
    assert Invoice().line_items == []


def test_distribution_rejects_capital_call_fields() -> None:
    with pytest.raises(ValidationError):
        DistributionNotice.model_validate({"management_fee": "10.00"})
