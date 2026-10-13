from datetime import date
from decimal import Decimal
from pathlib import Path

from streamlit.testing.v1 import AppTest

from fund_notices.demo import NOT_SHOWN, choice_label, field_rows, show, without_frontmatter
from fund_notices.schema import AnswerFile, CapitalCallNotice, LineItem

APP = Path(__file__).resolve().parents[1] / "src" / "fund_notices" / "app.py"
Dataset = tuple[list[AnswerFile], list[AnswerFile]]


def test_show_keeps_every_digit_of_money() -> None:
    assert show(Decimal("1234567.10")) == "1,234,567.10"
    assert show(Decimal("0.001")) == "0.001"
    assert show(date(2026, 3, 15)) == "2026-03-15"
    assert show(None) == NOT_SHOWN
    item = LineItem(description="Audit", quantity=Decimal(2), unit_price=Decimal("10.50"))
    assert show([item]) == f"Audit: 2 x 10.50 = {NOT_SHOWN}"


def test_field_rows_mark_each_field_against_the_answer_file() -> None:
    truth = CapitalCallNotice(total_amount=Decimal("100.00"), fund_name="Fund A")
    found = CapitalCallNotice(total_amount=Decimal("100.50"), fund_name="Fund A")
    rows = {row["Field"]: row for row in field_rows(found, truth)}
    assert rows["fund_name"]["Match"] == "yes"
    assert rows["total_amount"]["Match"] == "NO"
    assert rows["total_amount"]["Found"] == "100.50"
    assert rows["total_amount"]["Answer file"] == "100.00"


def test_field_rows_without_an_answer_file_show_only_what_was_found() -> None:
    rows = field_rows(CapitalCallNotice(fund_name="Fund A"), None)
    assert set(rows[0]) == {"Field", "Found"}


def test_planted_errors_are_marked_in_the_list(dataset: Dataset) -> None:
    labels = [choice_label(answer) for answer in dataset[1]]
    assert sum("planted error" in label for label in labels) == 6


def test_frontmatter_is_removed_before_showing_a_page() -> None:
    page = "---\ntype: results\n---\n\n# Results\n"
    assert without_frontmatter(page) == "\n# Results\n"
    assert without_frontmatter("# No frontmatter\n") == "# No frontmatter\n"


def test_app_page_loads_without_errors() -> None:
    # Nothing is read until Read it is pressed, so this never calls Ollama.
    app = AppTest.from_file(str(APP), default_timeout=60)
    app.run()
    assert not app.exception
    assert app.title[0].value == "Fund Notices"
