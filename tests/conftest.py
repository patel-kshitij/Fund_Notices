import pytest

from fund_notices.schema import AnswerFile
from fund_notices.synth import build_dataset


@pytest.fixture(scope="session")
def dataset() -> tuple[list[AnswerFile], list[AnswerFile]]:
    """The real train and test sets, built once for the whole test run."""
    return build_dataset()
