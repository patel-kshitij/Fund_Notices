"""Find the train documents most like a new one.

Two kinds of similarity, each used where it did better on the train set:
1. MiniLM embeddings give a second opinion on the type. They use different
   features from the TF-IDF classifier, so when the two disagree it means something.
2. TF-IDF word scores pick the worked example for extraction. Among documents of
   one type, the nearest by TF-IDF shared the page layout far more often.
Only train documents are in the pool. See docs/DECISIONS.md, entries 3 and 18.
"""

from collections.abc import Callable
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from sentence_transformers import SentenceTransformer
from sklearn.pipeline import Pipeline

from fund_notices.extract import Example
from fund_notices.schema import AnswerFile, DocType

MINILM = "sentence-transformers/all-MiniLM-L6-v2"

# Turns texts into one row of numbers per text, each row of length 1.
Embedder = Callable[[list[str]], NDArray[np.float32]]


def minilm_embedder(cache: Path) -> Embedder:
    """Load MiniLM from the project cache. Only the first run downloads it.

    The cache is inside the project, never a global folder. Once the model is
    there, it loads without contacting the internet.
    """
    try:
        model = SentenceTransformer(MINILM, cache_folder=str(cache), local_files_only=True)
    except OSError:
        model = SentenceTransformer(MINILM, cache_folder=str(cache))

    def embed(texts: list[str]) -> NDArray[np.float32]:
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors, dtype=np.float32)

    return embed


class TrainPool:
    """The train documents, ready to be compared with a new document."""

    def __init__(
        self, texts: list[str], answers: list[AnswerFile], classifier: Pipeline, embed: Embedder
    ) -> None:
        if len(texts) != len(answers):
            raise ValueError("texts and answers must have the same length")
        if any(answer.split != "train" for answer in answers):
            raise ValueError("the pool holds train documents only")
        self.texts = texts
        self.answers = answers
        self.embed = embed
        self.meanings = embed(texts)
        # The classifier's own TF-IDF, fitted on these same train texts. Its rows
        # have length 1, so a dot product between two rows is their cosine similarity.
        self.vectorizer = classifier.named_steps["tfidfvectorizer"]
        self.words = self.vectorizer.transform(texts)

    def nearest_type(self, text: str) -> DocType:
        """The type of the train document closest in meaning, by MiniLM."""
        scores = self.meanings @ self.embed([text])[0]
        return self.answers[int(scores.argmax())].doc_type

    def example(self, text: str, doc_type: DocType) -> Example:
        """The train document of this type with the most similar words, by TF-IDF.

        A train document is never its own example, because that would show the
        model the answer. This only matters when a train document is read.
        """
        scores = (self.words @ self.vectorizer.transform([text]).T).toarray().ravel()
        candidates = [
            i
            for i, answer in enumerate(self.answers)
            if answer.doc_type == doc_type and self.texts[i] != text
        ]
        best = max(candidates, key=lambda i: scores[i])
        answer = self.answers[best]
        return Example(doc_id=answer.doc_id, text=self.texts[best], fields=answer.fields)
