import io
from decimal import Decimal

from pypdf import PdfReader

from fund_notices.render import SYNTHETIC_LINE, render_pdf
from fund_notices.schema import AnswerFile, DocType, Invoice

Dataset = tuple[list[AnswerFile], list[AnswerFile]]


def pdf_pages(answer: AnswerFile) -> list[str]:
    reader = PdfReader(io.BytesIO(render_pdf(answer)))
    return [page.extract_text() for page in reader.pages]


def money_values(answer: AnswerFile) -> list[Decimal]:
    f = answer.fields
    values = [v for v in f.model_dump().values() if isinstance(v, Decimal)]
    if isinstance(f, Invoice):
        for item in f.line_items:
            values += [v for v in (item.unit_price, item.amount) if v is not None]
    return values


def test_every_page_carries_the_synthetic_line(dataset: Dataset) -> None:
    for answer in [*dataset[0], *dataset[1]]:
        for page in pdf_pages(answer):
            assert SYNTHETIC_LINE in page, answer.doc_id


def test_every_money_value_in_the_answer_is_printed(dataset: Dataset) -> None:
    for answer in dataset[1]:
        text = "\n".join(pdf_pages(answer))
        for value in money_values(answer):
            assert f"{value:,.2f}" in text, (answer.doc_id, value)


def test_names_are_printed(dataset: Dataset) -> None:
    for answer in dataset[1]:
        text = "\n".join(pdf_pages(answer))
        f = answer.fields
        names = [f.vendor_name, f.invoice_number] if isinstance(f, Invoice) else [f.investor_name]
        for name in names:
            assert name is not None and name in text, answer.doc_id


def test_untitled_documents_show_no_title(dataset: Dataset) -> None:
    for answer in dataset[1]:
        if answer.title is None:
            text = "\n".join(pdf_pages(answer)).lower()
            assert "notice\n" not in text.split("faketown", 1)[1][:40]


def test_same_document_renders_the_same_text(dataset: Dataset) -> None:
    answer = dataset[1][0]
    assert pdf_pages(answer) == pdf_pages(answer)


def test_only_capital_calls_warn_about_late_payment(dataset: Dataset) -> None:
    for answer in [*dataset[0], *dataset[1]]:
        if answer.doc_type != DocType.CAPITAL_CALL:
            assert "Late payments" not in "\n".join(pdf_pages(answer)), answer.doc_id
