"""Typed shapes for the data we pull out of each document.

These models check types only: is this a number, is this a date. They never check
business rules such as "the split adds up to the total". That job belongs to the
math checks, so the extractor can report exactly what a wrong document says.
See docs/DECISIONS.md, entry 4, and docs/reference/data-format.md.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class DocType(StrEnum):
    CAPITAL_CALL = "capital_call"
    DISTRIBUTION = "distribution"
    INVOICE = "invoice"


class _Strict(BaseModel):
    # Unknown keys are an error, so a misspelled field name fails loudly
    # instead of being dropped without a trace.
    model_config = ConfigDict(extra="forbid")


class NoticeBase(_Strict):
    """Fields that every ILPA notice shares, capital call or distribution."""

    fund_name: str | None = None
    investor_name: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    commitment: Decimal | None = None
    unfunded_commitment_before: Decimal | None = None
    unfunded_commitment_after: Decimal | None = None
    cumulative_contributions_before: Decimal | None = None
    cumulative_distributions_before: Decimal | None = None
    total_amount: Decimal | None = None


class CapitalCallNotice(NoticeBase):
    """A notice asking the investor to pay money in, split by what it pays for."""

    investments: Decimal | None = None
    management_fee: Decimal | None = None
    partnership_expenses: Decimal | None = None


class DistributionNotice(NoticeBase):
    """A notice paying money out to the investor, split by where it came from."""

    return_of_capital: Decimal | None = None
    realized_gain: Decimal | None = None
    income: Decimal | None = None


class LineItem(_Strict):
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None


class Invoice(_Strict):
    """A bill from a service provider to the fund."""

    vendor_name: str | None = None
    bill_to: str | None = None
    invoice_number: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None


ExtractedFields = CapitalCallNotice | DistributionNotice | Invoice

MODEL_FOR_TYPE: dict[DocType, type[ExtractedFields]] = {
    DocType.CAPITAL_CALL: CapitalCallNotice,
    DocType.DISTRIBUTION: DistributionNotice,
    DocType.INVOICE: Invoice,
}


ErrorKind = Literal["split_total_mismatch", "unfunded_after_mismatch"]


class PlantedError(_Strict):
    """A math mistake the generator put into a document on purpose."""

    kind: ErrorKind
    field: str
    correct_value: Decimal
    printed_value: Decimal


class AnswerFile(_Strict):
    """The true contents of one generated PDF. See docs/reference/data-format.md."""

    doc_id: str
    split: Literal["train", "test"]
    doc_type: DocType
    layout: int
    title: str | None
    fields: ExtractedFields
    planted_error: PlantedError | None = None

    @field_validator("fields", mode="before")
    @classmethod
    def _parse_fields_by_type(cls, value: object, info: ValidationInfo) -> object:
        # Pick the model from doc_type. Without this, a notice that only has
        # shared fields would fit both notice models and Pydantic would guess.
        doc_type = info.data.get("doc_type")
        if isinstance(value, dict) and doc_type in MODEL_FOR_TYPE:
            return MODEL_FOR_TYPE[doc_type].model_validate(value)
        return value
