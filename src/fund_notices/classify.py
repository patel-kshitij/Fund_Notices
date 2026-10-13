"""Sort a document into capital call, distribution, or invoice from its text.

This is the baseline: TF-IDF word scores fed into logistic regression.
TF-IDF gives each word a score per document. A word scores high when it is
frequent in this document and rare across the others. Logistic regression then
learns which words point to which type.

It trains on the train set only, so the test set stays unseen. See
docs/DECISIONS.md, entry 3.
"""

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline

from fund_notices.schema import AnswerFile, DocType

# Words of 2 or more letters. Numbers are left out, because amounts, dates, and
# references are random and say nothing about the type.
WORDS_ONLY = r"\b[A-Za-z]{2,}\b"


@dataclass(frozen=True)
class Prediction:
    doc_type: DocType
    confidence: float


def train_classifier(texts: list[str], answers: list[AnswerFile]) -> Pipeline:
    """Fit the classifier on train documents. texts[i] is the text of answers[i]."""
    if len(texts) != len(answers):
        raise ValueError("texts and answers must have the same length")
    if any(answer.split != "train" for answer in answers):
        raise ValueError("the classifier trains on train documents only")
    model = make_pipeline(
        # Single words and pairs of words, so "capital call" counts as well as "call".
        TfidfVectorizer(token_pattern=WORDS_ONLY, ngram_range=(1, 2)),
        LogisticRegression(max_iter=1000),
    )
    model.fit(texts, [str(answer.doc_type) for answer in answers])
    return model


def predict(model: Pipeline, text: str) -> Prediction:
    """Return the most likely type for one text, and the model's probability for it."""
    probabilities = model.predict_proba([text])[0]
    best = probabilities.argmax()
    return Prediction(doc_type=DocType(model.classes_[best]), confidence=float(probabilities[best]))
