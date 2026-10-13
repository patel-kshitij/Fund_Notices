import hashlib

import numpy as np
import pytest
from numpy.typing import NDArray

from fund_notices.classify import train_classifier
from fund_notices.retrieve import TrainPool
from fund_notices.schema import MODEL_FOR_TYPE, AnswerFile, DocType

Dataset = tuple[list[AnswerFile], list[AnswerFile]]
Texts = tuple[list[str], list[str]]


def hash_embed(texts: list[str]) -> NDArray[np.float32]:
    """A fake embedder with no download: each distinct text gets its own fixed direction."""
    rows = []
    for text in texts:
        seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
        vector = np.random.default_rng(seed).normal(size=16)
        rows.append(vector / np.linalg.norm(vector))
    return np.array(rows, dtype=np.float32)


@pytest.fixture(scope="module")
def pool(dataset: Dataset, texts: Texts) -> TrainPool:
    classifier = train_classifier(texts[0], dataset[0])
    return TrainPool(texts[0], dataset[0], classifier, hash_embed)


def test_pool_refuses_test_documents(dataset: Dataset, texts: Texts) -> None:
    classifier = train_classifier(texts[0], dataset[0])
    with pytest.raises(ValueError, match="train documents only"):
        TrainPool([*texts[0], texts[1][0]], [*dataset[0], dataset[1][0]], classifier, hash_embed)


def test_nearest_type_is_the_type_of_the_closest_train_document(
    pool: TrainPool, dataset: Dataset, texts: Texts
) -> None:
    # Each train text is closest to itself, so the answer is its own type.
    for text, answer in zip(texts[0], dataset[0], strict=True):
        assert pool.nearest_type(text) == answer.doc_type


def test_example_is_a_train_document_of_the_asked_type(pool: TrainPool, texts: Texts) -> None:
    for text in texts[1][:6]:
        for doc_type in DocType:
            example = pool.example(text, doc_type)
            assert example.doc_id.startswith("train_")
            assert type(example.fields) is MODEL_FOR_TYPE[doc_type]


def test_example_is_the_train_document_with_the_most_similar_words(
    pool: TrainPool, dataset: Dataset, texts: Texts
) -> None:
    # Doubling a space changes the text but not its words, so the copy is
    # closest to the train document it came from.
    for text, answer in zip(texts[0], dataset[0], strict=True):
        copy = text.replace("SYNTHETIC SAMPLE", "SYNTHETIC  SAMPLE")
        assert pool.example(copy, answer.doc_type).doc_id == answer.doc_id


def test_a_train_document_is_never_its_own_example(
    pool: TrainPool, dataset: Dataset, texts: Texts
) -> None:
    for text, answer in zip(texts[0], dataset[0], strict=True):
        example = pool.example(text, answer.doc_type)
        assert example.doc_id != answer.doc_id
        assert type(example.fields) is type(answer.fields)
