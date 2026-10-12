"""Draw one AnswerFile as a PDF.

The answer file says what the document contains. This module decides how it
looks: the layout, the labels, the date and money formats, and the filler text.
Those choices come from a random generator seeded with the document id, so the
same document always looks the same.
"""

import random
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from fund_notices.schema import (
    AnswerFile,
    CapitalCallNotice,
    DistributionNotice,
    DocType,
    Invoice,
    NoticeBase,
)
from fund_notices.synth import SEED

SYNTHETIC_LINE = "SYNTHETIC SAMPLE, NOT A REAL NOTICE"

LABELS: dict[str, tuple[str, ...]] = {
    "issue_date": ("Notice Date", "Date", "Issue Date", "Date of Notice"),
    "call_due": ("Due Date", "Payment Due", "Settlement Date", "Funding Date"),
    "dist_due": ("Payment Date", "Distribution Date", "Settlement Date", "Value Date"),
    "commitment": ("Commitment", "Total Commitment", "Capital Commitment", "LP Commitment"),
    "unfunded_commitment_before": (
        "Unfunded Commitment Before This Notice",
        "Remaining Commitment, Beginning",
        "Unfunded Commitment (prior)",
    ),
    "unfunded_commitment_after": (
        "Unfunded Commitment After This Notice",
        "Remaining Commitment, Ending",
        "Unfunded Commitment (after)",
    ),
    "cumulative_contributions_before": (
        "Cumulative Contributions (prior)",
        "Capital Contributed to Date",
        "Total Paid-In Before This Notice",
    ),
    "cumulative_distributions_before": (
        "Cumulative Distributions (prior)",
        "Distributions Received to Date",
        "Total Distributed Before This Notice",
    ),
    "investments": ("Investments", "Portfolio Investments", "Capital for Investments"),
    "management_fee": ("Management Fee", "Management Fees", "Advisory Fee"),
    "partnership_expenses": ("Partnership Expenses", "Fund Expenses", "Operating Expenses"),
    "return_of_capital": ("Return of Capital", "Capital Returned", "Return of Contributed Capital"),
    "realized_gain": ("Realized Gain", "Capital Gains", "Realized Gain on Investments"),
    "income": ("Income", "Dividend and Interest Income", "Investment Income"),
    "call_total": ("Total Amount Due", "Total Capital Call", "Amount of This Drawdown"),
    "dist_total": ("Total Distribution", "Net Distribution Amount", "Amount Distributed to You"),
}

BOILERPLATE = (
    "This notice is delivered under the Limited Partnership Agreement of the Fund. "
    "Capitalized terms not defined here have the meanings given in that agreement.",
    "This document is confidential and intended only for the named investor. "
    "Please do not forward it.",
    "Questions about this notice may be sent to investor.relations@example.com.",
    "Past performance is not a guide to future results. Amounts are unaudited.",
)
# Only a capital call asks the investor to pay, so only it warns about late payment.
LATE_PAYMENT = (
    "Late payments may bear interest at the rate set out in the Limited Partnership Agreement."
)

DATE_FORMATS: tuple[Callable[[date], str], ...] = (
    lambda d: f"{d.day} {d:%B %Y}",
    lambda d: f"{d:%B} {d.day}, {d.year}",
    lambda d: d.isoformat(),
    lambda d: f"{d:%d-%b-%Y}",
)


class Style:
    """The look of one document, chosen once so every line is consistent."""

    def __init__(self, rng: random.Random, currency: str | None) -> None:
        self.rng = rng
        self.currency = currency or ""
        self.date_format = rng.choice(DATE_FORMATS)
        self.money_style = rng.randrange(3)
        self.labels = {key: rng.choice(options) for key, options in LABELS.items()}

    def money(self, value: Decimal | None) -> str:
        if value is None:
            return ""
        number = f"{value:,.2f}"
        if self.money_style == 0:
            return f"{self.currency} {number}"
        if self.money_style == 1:
            return f"{number} {self.currency}"
        return number

    def day(self, value: date | None) -> str:
        return "" if value is None else self.date_format(value)


class NoticePDF(FPDF):
    def footer(self) -> None:
        # Every page carries the synthetic label, so no page can be mistaken for real.
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"{SYNTHETIC_LINE}    Page {self.page_no()}", align="C")


def _line(pdf: FPDF, text: str, size: int = 10, style: str = "", height: float = 6) -> None:
    pdf.set_font("helvetica", style, size)
    pdf.multi_cell(0, height, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _row(pdf: FPDF, label: str, value: str, bold: bool = False) -> None:
    pdf.set_font("helvetica", "B" if bold else "", 10)
    pdf.cell(110, 7, label, border="B")
    pdf.cell(0, 7, value, border="B", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _wire_block(pdf: FPDF, reference: str) -> None:
    _line(pdf, "Wire instructions", style="B")
    _line(pdf, "Bank: First Imaginary Bank of Nowhere (FAKE)")
    _line(pdf, "Account: 000000000 (FAKE)    SWIFT: FAKEXX00")
    _line(pdf, f"Reference: {reference}")


def _filler(pdf: FPDF, rng: random.Random, is_call: bool = False) -> None:
    pdf.ln(4)
    pool = (*BOILERPLATE, LATE_PAYMENT) if is_call else BOILERPLATE
    for text in rng.sample(pool, 3):
        _line(pdf, text, size=8, height=4)
        pdf.ln(1)


def _notice_rows(answer: AnswerFile, s: Style) -> tuple[list[tuple[str, str]], tuple[str, str]]:
    """The split rows and the total row for this notice."""
    f = answer.fields
    if isinstance(f, CapitalCallNotice):
        split = [
            (s.labels["investments"], s.money(f.investments)),
            (s.labels["management_fee"], s.money(f.management_fee)),
            (s.labels["partnership_expenses"], s.money(f.partnership_expenses)),
        ]
        return split, (s.labels["call_total"], s.money(f.total_amount))
    assert isinstance(f, DistributionNotice)
    split = [
        (s.labels["return_of_capital"], s.money(f.return_of_capital)),
        (s.labels["realized_gain"], s.money(f.realized_gain)),
        (s.labels["income"], s.money(f.income)),
    ]
    return split, (s.labels["dist_total"], s.money(f.total_amount))


def _account_rows(f: NoticeBase, s: Style) -> list[tuple[str, str]]:
    return [
        (s.labels["commitment"], s.money(f.commitment)),
        (s.labels["cumulative_contributions_before"], s.money(f.cumulative_contributions_before)),
        (s.labels["cumulative_distributions_before"], s.money(f.cumulative_distributions_before)),
        (s.labels["unfunded_commitment_before"], s.money(f.unfunded_commitment_before)),
        (s.labels["unfunded_commitment_after"], s.money(f.unfunded_commitment_after)),
    ]


def _render_notice(pdf: FPDF, answer: AnswerFile, s: Style, rng: random.Random) -> None:
    f = answer.fields
    assert isinstance(f, NoticeBase)
    is_call = answer.doc_type == DocType.CAPITAL_CALL
    due_label = s.labels["call_due" if is_call else "dist_due"]
    split, total = _notice_rows(answer, s)
    account = _account_rows(f, s)

    _line(pdf, f.fund_name or "", size=12, style="B")
    _line(pdf, "c/o Imaginary Fund Services, 1 Nowhere Lane, Faketown", size=8)
    pdf.ln(4)
    if answer.title:
        _line(pdf, answer.title.upper() if answer.layout == 2 else answer.title, 16, "B", 9)
        pdf.ln(2)

    if answer.layout == 0:
        # Layout 0: header lines, then one table with everything.
        _line(pdf, f"To: {f.investor_name}")
        _line(pdf, f"{s.labels['issue_date']}: {s.day(f.issue_date)}")
        _line(pdf, f"{due_label}: {s.day(f.due_date)}")
        _line(pdf, f"Currency: {f.currency}")
        pdf.ln(3)
        for label, value in [*split, total, *account]:
            _row(pdf, label, value, bold=(label, value) == total)

    elif answer.layout == 1:
        # Layout 1: a letter, with the key numbers inside sentences.
        _line(pdf, s.day(f.issue_date))
        pdf.ln(2)
        _line(pdf, f"Dear {f.investor_name},")
        pdf.ln(2)
        verb = "calls capital from" if is_call else "will distribute to"
        _line(
            pdf,
            f"{f.fund_name} {verb} you a total of {s.money(f.total_amount)}"
            f"{f' ({f.currency})' if s.money_style == 2 else ''}. "
            f"The {due_label.lower()} is {s.day(f.due_date)}. "
            "The amount is made up as follows.",
        )
        pdf.ln(2)
        for label, value in split:
            _line(pdf, f"    {label}: {value}")
        pdf.ln(2)
        _line(pdf, "Your account with the Fund", style="B")
        for label, value in account:
            _line(pdf, f"    {label}: {value}")

    else:
        # Layout 2: a statement in two sections, with the total first.
        _line(pdf, f"Investor: {f.investor_name}    Currency: {f.currency}")
        _line(
            pdf,
            f"{s.labels['issue_date']}: {s.day(f.issue_date)}    {due_label}: {s.day(f.due_date)}",
        )
        pdf.ln(3)
        _line(pdf, "Detail of This Notice", style="B")
        _row(pdf, *total, bold=True)
        for label, value in split:
            _row(pdf, label, value)
        pdf.ln(3)
        _line(pdf, "Investor Account Summary", style="B")
        for label, value in account:
            _row(pdf, label, value)

    pdf.ln(4)
    if is_call:
        _wire_block(pdf, f"REF-{rng.randint(100000, 999999)}")
    _filler(pdf, rng, is_call)


def _render_invoice(pdf: FPDF, answer: AnswerFile, s: Style, rng: random.Random) -> None:
    f = answer.fields
    assert isinstance(f, Invoice)
    tax_label = rng.choice(("Tax", "VAT", "Sales Tax"))

    _line(pdf, f.vendor_name or "", size=12, style="B")
    _line(pdf, "99 Imaginary Road, Faketown", size=8)
    pdf.ln(4)
    if answer.title:
        _line(pdf, answer.title, 16, "B", 9)
        pdf.ln(2)
    _line(pdf, f"Bill To: {f.bill_to}")
    _line(pdf, f"Invoice No.: {f.invoice_number}")
    _line(pdf, f"Invoice Date: {s.day(f.issue_date)}    Payment Due: {s.day(f.due_date)}")
    _line(pdf, f"Currency: {f.currency}")
    pdf.ln(3)

    if answer.layout == 0:
        # Layout 0: a full table with quantity and unit price columns.
        pdf.set_font("helvetica", "B", 10)
        for text, width in (("Description", 80), ("Qty", 20), ("Unit Price", 40), ("Amount", 0)):
            pdf.cell(width, 7, text, border="B")
        pdf.ln()
        pdf.set_font("helvetica", "", 10)
        for item in f.line_items:
            pdf.cell(80, 7, item.description or "")
            pdf.cell(20, 7, f"{item.quantity}")
            pdf.cell(40, 7, s.money(item.unit_price))
            pdf.cell(0, 7, s.money(item.amount), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    elif answer.layout == 1:
        # Layout 1: one sentence per line item, as hours worked.
        _line(pdf, "Professional services rendered", style="B")
        for item in f.line_items:
            _line(
                pdf,
                f"{item.description}: {item.quantity} hours at {s.money(item.unit_price)} "
                f"per hour = {s.money(item.amount)}",
            )
    else:
        # Layout 2: compact rows with quantity times unit price in the label.
        for item in f.line_items:
            label = f"{item.description} ({item.quantity} x {s.money(item.unit_price)})"
            _row(pdf, label, s.money(item.amount))

    pdf.ln(3)
    _row(pdf, "Subtotal", s.money(f.subtotal))
    _row(pdf, tax_label, s.money(f.tax))
    _row(pdf, "Total Due", s.money(f.total), bold=True)
    pdf.ln(4)
    _wire_block(pdf, f.invoice_number or "")
    _line(pdf, "Payment terms: 30 days. Thank you for your business.", size=8)


def render_pdf(answer: AnswerFile) -> bytes:
    """Return the PDF bytes for one answer file."""
    rng = random.Random(f"{SEED}-{answer.doc_id}")
    style = Style(rng, answer.fields.currency)
    pdf = NoticePDF()
    pdf.set_creation_date(datetime(2026, 1, 1, tzinfo=UTC))
    pdf.add_page()
    if answer.doc_type == DocType.INVOICE:
        _render_invoice(pdf, answer, style, rng)
    else:
        _render_notice(pdf, answer, style, rng)
    return bytes(pdf.output())
