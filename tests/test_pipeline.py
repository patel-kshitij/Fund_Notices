import dataclasses
from typing import Any

import pytest

from fund_notices.checks import CHECK_FOR_ERROR, Problem
from fund_notices.classify import Prediction, train_classifier
from fund_notices.extract import ExtractionResult, answer_json
from fund_notices.pipeline import NoticeReader, Outcome
from fund_notices.retrieve import TrainPool
from fund_notices.schema import AnswerFile, DocType, Invoice
from test_retrieve import hash_embed

Dataset = tuple[list[AnswerFile], list[AnswerFile]]
Texts = tuple[list[str], list[str]]


class FakeClient:
    """A fake model that always gives the same reply and records each prompt."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    @property
    def name(self) -> str:
        return "fake"

    def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        self.prompts.append(prompt)
        return self.reply


CLEAN = Outcome(
    prediction=Prediction(DocType.INVOICE, 0.6),
    second_opinion=DocType.INVOICE,
    example_id=None,
    extraction=ExtractionResult(fields=Invoice(), attempts=1),
    problems=[],
)


def test_agreeing_types_and_clean_numbers_need_no_review() -> None:
    assert not CLEAN.needs_review and CLEAN.review_reasons == []


def test_each_reason_on_its_own_sends_a_document_to_a_person() -> None:
    unsure = dataclasses.replace(CLEAN, second_opinion=DocType.CAPITAL_CALL)
    failed = dataclasses.replace(CLEAN, extraction=ExtractionResult(None, 2, "bad JSON"))
    wrong = dataclasses.replace(CLEAN, problems=[Problem("total", "subtotal + tax is not total")])
    for outcome, words in ((unsure, "type unsure"), (failed, "failed"), (wrong, "total:")):
        assert outcome.needs_review
        assert words in outcome.review_reasons[0]


@pytest.fixture(scope="module")
def parts(dataset: Dataset, texts: Texts) -> tuple[Any, TrainPool]:
    classifier = train_classifier(texts[0], dataset[0])
    return classifier, TrainPool(texts[0], dataset[0], classifier, hash_embed)


def planted_document(dataset: Dataset, texts: Texts) -> tuple[str, AnswerFile]:
    """The first test document with a planted error and a title."""
    for text, answer in zip(texts[1], dataset[1], strict=True):
        if answer.planted_error is not None and answer.title is not None:
            return text, answer
    raise AssertionError("no titled document with a planted error")


def test_reader_sends_a_planted_error_to_a_person(
    parts: tuple[Any, TrainPool], dataset: Dataset, texts: Texts
) -> None:
    text, answer = planted_document(dataset, texts)
    assert answer.planted_error is not None
    # The fake model copies the page perfectly, wrong number included.
    client = FakeClient(answer_json(answer.fields.model_dump()))
    outcome = NoticeReader(*parts, client).read(text)
    assert outcome.extraction.fields == answer.fields
    assert CHECK_FOR_ERROR[answer.planted_error.kind] in {p.check for p in outcome.problems}
    assert outcome.needs_review
    assert outcome.example_id is not None and outcome.example_id.startswith("train_")
    assert "Worked example" in client.prompts[0]


def test_reader_without_examples_shows_none(
    parts: tuple[Any, TrainPool], dataset: Dataset, texts: Texts
) -> None:
    text, answer = planted_document(dataset, texts)
    client = FakeClient(answer_json(answer.fields.model_dump()))
    outcome = NoticeReader(*parts, client, use_examples=False).read(text)
    assert outcome.example_id is None
    assert "Worked example" not in client.prompts[0]
