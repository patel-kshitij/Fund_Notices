from decimal import Decimal
from typing import Any

from fund_notices.extract import (
    Example,
    answer_json,
    build_prompt,
    extract,
    model_schema,
    numbers_only,
)
from fund_notices.pdftext import pdf_text
from fund_notices.render import SYNTHETIC_LINE, render_pdf
from fund_notices.schema import AnswerFile, CapitalCallNotice, DocType, Invoice, LineItem
from fund_notices.score import amounts_wrong, field_matches

Dataset = tuple[list[AnswerFile], list[AnswerFile]]


class FakeClient:
    """A fake model that gives canned replies in order and records each prompt."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.prompts: list[str] = []

    @property
    def name(self) -> str:
        return "fake"

    def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        self.prompts.append(prompt)
        return self.replies[len(self.prompts) - 1]


def test_pdf_text_reads_the_rendered_page(dataset: Dataset) -> None:
    answer = dataset[1][0]
    text = pdf_text(render_pdf(answer))
    assert SYNTHETIC_LINE in text


def test_good_reply_is_accepted_on_the_first_attempt() -> None:
    client = FakeClient(['{"total_amount": 106473.60, "currency": "EUR"}'])
    result = extract("some text", DocType.CAPITAL_CALL, client)
    assert result.attempts == 1 and result.error is None
    assert isinstance(result.fields, CapitalCallNotice)
    assert result.fields.total_amount == Decimal("106473.60")


def test_bad_reply_is_retried_once_with_the_error() -> None:
    client = FakeClient(['{"total_amount": "106,473.60 EUR"}', '{"total_amount": 106473.60}'])
    result = extract("some text", DocType.CAPITAL_CALL, client)
    assert result.attempts == 2 and result.fields is not None
    assert "106,473.60 EUR" in client.prompts[1]
    assert "total_amount" in client.prompts[1]


def test_two_bad_replies_give_up_and_report_the_error() -> None:
    client = FakeClient(['{"total": 1}', '{"total": 1}', '{"total": 1}'])
    result = extract("some text", DocType.CAPITAL_CALL, client)
    assert result.fields is None and result.attempts == 2
    assert result.error is not None and "total" in result.error
    assert len(client.prompts) == 2


def test_wrong_numbers_are_kept_as_printed() -> None:
    reply = (
        '{"investments": 10, "management_fee": 1, "partnership_expenses": 1, "total_amount": 99}'
    )
    result = extract("some text", DocType.CAPITAL_CALL, FakeClient([reply]))
    assert isinstance(result.fields, CapitalCallNotice)
    assert result.fields.total_amount == Decimal(99)


def test_schema_sent_to_the_model_allows_only_numbers_for_money() -> None:
    schema = numbers_only(Invoice.model_json_schema())
    assert {"type": "string"} not in schema["properties"]["total"]["anyOf"]
    assert {"type": "string"} not in schema["$defs"]["LineItem"]["properties"]["amount"]["anyOf"]
    assert {"type": "string"} in schema["properties"]["vendor_name"]["anyOf"]


def test_prompt_holds_the_text_and_the_fields_for_the_type() -> None:
    prompt = build_prompt("PAGE TEXT", DocType.DISTRIBUTION)
    assert "PAGE TEXT" in prompt and "realized_gain" in prompt
    assert "management_fee" not in prompt


def test_score_compares_money_by_value_and_fails_a_missing_extraction() -> None:
    want = CapitalCallNotice(total_amount=Decimal("100.50"), fund_name="Fund A")
    got = CapitalCallNotice(total_amount=Decimal("100.5"), fund_name=" Fund A ")
    assert all(field_matches(want, got).values())
    assert not any(field_matches(want, None).values())
    wrong = CapitalCallNotice(total_amount=Decimal("100.51"), fund_name="Fund A")
    assert field_matches(want, wrong)["total_amount"] is False


def test_schema_sent_to_the_model_requires_every_key() -> None:
    schema = model_schema(DocType.INVOICE)
    assert set(schema["required"]) == set(Invoice.model_fields)
    line_item = schema["$defs"]["LineItem"]
    assert set(line_item["required"]) == set(line_item["properties"])


def test_example_answer_is_exact_json_with_unquoted_money(dataset: Dataset) -> None:
    answer = next(a for a in dataset[0] if isinstance(a.fields, Invoice))
    assert isinstance(answer.fields, Invoice) and answer.fields.total is not None
    text = answer_json(answer.fields.model_dump())
    assert Invoice.model_validate_json(text) == answer.fields
    assert f'"total": {answer.fields.total}' in text


def test_prompt_shows_the_worked_example_before_the_document() -> None:
    fields = CapitalCallNotice(total_amount=Decimal("5.10"))
    example = Example(doc_id="train_001", text="EXAMPLE TEXT", fields=fields)
    prompt = build_prompt("REAL TEXT", DocType.CAPITAL_CALL, example)
    assert prompt.index("EXAMPLE TEXT") < prompt.index("REAL TEXT")
    assert '"total_amount": 5.10' in prompt
    assert "Worked example" not in build_prompt("REAL TEXT", DocType.CAPITAL_CALL)


def test_amounts_wrong_counts_money_and_line_item_numbers() -> None:
    line = LineItem(quantity=Decimal(2), unit_price=Decimal(10), amount=Decimal(20))
    truth = Invoice(line_items=[line, line], total=Decimal(40), vendor_name="A")
    assert amounts_wrong(truth, truth.model_copy()) == 0
    off = line.model_copy(update={"amount": Decimal(21)})
    got = Invoice(line_items=[off], total=Decimal(41), vendor_name="B")
    # The total, one line amount, and the 3 numbers of the missing line. The name is text.
    assert amounts_wrong(truth, got) == 5
    assert amounts_wrong(truth, None) == 1 + 6
