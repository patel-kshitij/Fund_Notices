import pytest
from sklearn.pipeline import Pipeline

from fund_notices.classify import predict, train_classifier
from fund_notices.schema import AnswerFile, DocType

Dataset = tuple[list[AnswerFile], list[AnswerFile]]
Texts = tuple[list[str], list[str]]


@pytest.fixture(scope="module")
def model(dataset: Dataset, texts: Texts) -> Pipeline:
    return train_classifier(texts[0], dataset[0])


def test_refuses_to_train_on_test_documents(dataset: Dataset, texts: Texts) -> None:
    with pytest.raises(ValueError, match="train documents only"):
        train_classifier([*texts[0], texts[1][0]], [*dataset[0], dataset[1][0]])


def test_refuses_texts_and_answers_of_different_lengths(dataset: Dataset, texts: Texts) -> None:
    with pytest.raises(ValueError, match="same length"):
        train_classifier(texts[0][:-1], dataset[0])


def test_numbers_are_not_features(model: Pipeline) -> None:
    vocabulary = model.named_steps["tfidfvectorizer"].vocabulary_
    assert not [term for term in vocabulary if any(ch.isdigit() for ch in term)]


def test_training_is_repeatable(dataset: Dataset, texts: Texts, model: Pipeline) -> None:
    again = train_classifier(texts[0], dataset[0])
    assert (model.predict_proba(texts[1]) == again.predict_proba(texts[1])).all()


def test_predict_returns_the_top_type_and_its_probability(texts: Texts, model: Pipeline) -> None:
    for text in texts[1]:
        prediction = predict(model, text)
        probabilities = model.predict_proba([text])[0]
        best = probabilities.argmax()
        assert prediction.doc_type == DocType(model.classes_[best])
        assert prediction.confidence == pytest.approx(probabilities[best])
        assert isinstance(prediction.doc_type, DocType)
        assert isinstance(prediction.confidence, float)


def test_every_type_is_predicted_somewhere_in_the_test_set(texts: Texts, model: Pipeline) -> None:
    assert {predict(model, text).doc_type for text in texts[1]} == set(DocType)
