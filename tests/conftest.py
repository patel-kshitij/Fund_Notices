import pytest

from fund_notices.pdftext import pdf_text
from fund_notices.render import render_pdf
from fund_notices.schema import AnswerFile
from fund_notices.synth import build_dataset


@pytest.fixture(scope="session")
def dataset() -> tuple[list[AnswerFile], list[AnswerFile]]:
    """The real train and test sets, built once for the whole test run."""
    return build_dataset()


@pytest.fixture(scope="session")
def texts(dataset: tuple[list[AnswerFile], list[AnswerFile]]) -> tuple[list[str], list[str]]:
    """The text of every train and test PDF, read the same way the pipeline reads it."""
    train, test = dataset
    return (
        [pdf_text(render_pdf(a)) for a in train],
        [pdf_text(render_pdf(a)) for a in test],
    )
