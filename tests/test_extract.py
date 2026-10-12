from decimal import Decimal
from typing import Any

from fund_notices.extract import build_prompt, extract, numbers_only
from fund_notices.pdftext import pdf_text
from fund_notices.render import SYNTHETIC_LINE, render_pdf
from fund_notices.schema import AnswerFile, CapitalCallNotice, DocType, Invoice
from fund_notices.score import field_matches

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
