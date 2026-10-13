"""The whole pipeline for one document: type, fields, math checks, and the review decision.

A document goes to a person when any of these is true:
1. The TF-IDF classifier and the MiniLM nearest neighbour disagree on the type.
2. Extraction failed twice.
3. A math check found a problem, including a number it needed but could not find.
See docs/DECISIONS.md, entry 19.
"""

from dataclasses import dataclass
from pathlib import Path

from sklearn.pipeline import Pipeline

from fund_notices.checks import Problem, check
from fund_notices.classify import Prediction, predict, train_classifier
from fund_notices.extract import ExtractionResult, extract
from fund_notices.llm import LLMClient
from fund_notices.pdftext import pdf_text
from fund_notices.retrieve import Embedder, TrainPool
from fund_notices.schema import AnswerFile, DocType


@dataclass
class Outcome:
    """Everything the pipeline found out about one document."""

    prediction: Prediction
    second_opinion: DocType
    example_id: str | None
    extraction: ExtractionResult
    problems: list[Problem]

    @property
    def review_reasons(self) -> list[str]:
        reasons = []
        if self.second_opinion != self.prediction.doc_type:
            reasons.append(
                f"type unsure: the words say {self.prediction.doc_type}, "
                f"the nearest train document is {self.second_opinion}"
            )
        if self.extraction.fields is None:
            reasons.append("extraction failed twice")
        reasons += [f"{p.check}: {p.detail}" for p in self.problems]
        return reasons

    @property
    def needs_review(self) -> bool:
        return bool(self.review_reasons)


def load_split(folder: Path) -> tuple[list[str], list[AnswerFile]]:
    """The text and answer file of every document in a folder, in file name order."""
    answers = [
        AnswerFile.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(folder.glob("*.json"))
    ]
    texts = [pdf_text(folder / f"{answer.doc_id}.pdf") for answer in answers]
    return texts, answers


class NoticeReader:
    """Reads one document at a time with a classifier and pool built from the train set."""

    def __init__(
        self, classifier: Pipeline, pool: TrainPool, client: LLMClient, use_examples: bool = True
    ) -> None:
        self.classifier = classifier
        self.pool = pool
        self.client = client
        self.use_examples = use_examples

    @classmethod
    def from_train(
        cls,
        texts: list[str],
        answers: list[AnswerFile],
        client: LLMClient,
        embed: Embedder,
        use_examples: bool = True,
    ) -> "NoticeReader":
        classifier = train_classifier(texts, answers)
        return cls(classifier, TrainPool(texts, answers, classifier, embed), client, use_examples)

    def read(self, text: str) -> Outcome:
        prediction = predict(self.classifier, text)
        example = self.pool.example(text, prediction.doc_type) if self.use_examples else None
        extraction = extract(text, prediction.doc_type, self.client, example)
        problems = [] if extraction.fields is None else check(extraction.fields)
        return Outcome(
            prediction=prediction,
            second_opinion=self.pool.nearest_type(text),
            example_id=None if example is None else example.doc_id,
            extraction=extraction,
            problems=problems,
        )
