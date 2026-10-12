"""Decide what every synthetic document says.

This module only builds the true values, as AnswerFile objects. It never draws a
PDF. render.py turns each AnswerFile into a PDF.

All names are invented. Clean documents always add up. Only the documents
listed in a planted error are wrong, and only in the way the error records.
"""

import random
from collections.abc import Callable
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fund_notices.schema import (
    AnswerFile,
    CapitalCallNotice,
    DistributionNotice,
    DocType,
    ErrorKind,
    ExtractedFields,
    Invoice,
    LineItem,
    NoticeBase,
    PlantedError,
)

SEED = 20261009
TRAIN_PER_TYPE = 14
TEST_PER_TYPE = 15
PLANTED_PER_NOTICE_TYPE = 3
CENT = Decimal("0.01")

FUND_NAMES = (
    "Quillfeather Capital Partners IV",
    "Marrowstone Growth Fund II",
    "Tidewren Infrastructure Fund I",
    "Larkspur Hollow Ventures III",
    "Copperfinch Credit Opportunities II",
    "Glimmerdale Buyout Fund V",
    "Ashvane Real Assets Fund I",
    "Brackenmoor Secondaries Fund III",
)
INVESTOR_NAMES = (
    "Brindlewood Family Office",
    "Kestrelmoor University Endowment",
    "Vantreen Foundation",
    "Ollerby County Employees Pension Plan",
    "Sablecourt Insurance Holdings",
    "Pennywhistle Teachers Retirement Trust",
    "Draymere Charitable Trust",
    "Fenwold Sovereign Reserve Fund",
)
VENDORS = {
    "Thistlebrook Audit LLP": ("Annual audit fieldwork", "Audit partner review", "K-1 preparation"),
    "Corvane Legal Services": ("Legal advice on side letters", "LPA amendment drafting"),
    "Lumenhart Fund Administration": ("Fund accounting services", "Investor reporting"),
    "Pebblecrest Valuation Advisors": ("Portfolio valuation review", "Fair value memo"),
}
CURRENCIES = ("USD", "EUR", "GBP")
TITLES = {
    DocType.CAPITAL_CALL: (
        "Capital Call Notice",
        "Drawdown Notice",
        "Notice of Capital Contribution",
    ),
    DocType.DISTRIBUTION: (
        "Distribution Notice",
        "Notice of Distribution",
        "Distribution Payment Notice",
    ),
    DocType.INVOICE: ("Invoice", "Tax Invoice", "Statement of Services"),
}


def shift_field[N: NoticeBase](fields: N, field_name: str, delta: Decimal) -> N:
    """Return a copy of fields with one money field moved by delta.

    The original object must stay unchanged.
    """
    current = getattr(fields, field_name)
    if current is None:
        raise ValueError(f"cannot shift {field_name}: it is empty")
    return fields.model_copy(update={field_name: current + delta})


def _pct(rng: random.Random, amount: Decimal, low_bp: int, high_bp: int) -> Decimal:
    """A random share of amount, between low_bp and high_bp basis points, in cents."""
    share = amount * Decimal(rng.randint(low_bp, high_bp)) / Decimal(10_000)
    return share.quantize(CENT, rounding=ROUND_HALF_UP)


def _dates(rng: random.Random, min_gap: int, max_gap: int) -> tuple[date, date]:
    issue = date(2025, 1, 6) + timedelta(days=rng.randint(0, 600))
    return issue, issue + timedelta(days=rng.randint(min_gap, max_gap))


def _account(rng: random.Random) -> tuple[Decimal, Decimal, Decimal]:
    """Commitment, cumulative contributions, and cumulative distributions before this notice."""
    commitment = Decimal(rng.randrange(1_000_000, 25_000_001, 250_000))
    contributed = _pct(rng, commitment, 1_000, 8_500)
    distributed = _pct(rng, commitment, 0, 4_000)
    return commitment, contributed, distributed


def make_capital_call(rng: random.Random) -> CapitalCallNotice:
    commitment, contributed, distributed = _account(rng)
    unfunded_before = commitment - contributed
    # Some calls pay fees and expenses only, with nothing for investments.
    investments = Decimal("0.00") if rng.random() < 0.15 else _pct(rng, commitment, 150, 900)
    fee = _pct(rng, commitment, 25, 50)
    expenses = Decimal(rng.randint(500_00, 60_000_00)) / 100
    total = investments + fee + expenses
    issue, due = _dates(rng, 10, 21)
    return CapitalCallNotice(
        fund_name=rng.choice(FUND_NAMES),
        investor_name=rng.choice(INVESTOR_NAMES),
        issue_date=issue,
        due_date=due,
        currency=rng.choice(CURRENCIES),
        commitment=commitment,
        unfunded_commitment_before=unfunded_before,
        unfunded_commitment_after=unfunded_before - total,
        cumulative_contributions_before=contributed,
        cumulative_distributions_before=distributed,
        total_amount=total,
        investments=investments,
        management_fee=fee,
        partnership_expenses=expenses,
    )


def make_distribution(rng: random.Random) -> DistributionNotice:
    commitment, contributed, distributed = _account(rng)
    unfunded = commitment - contributed
    return_of_capital = _pct(rng, commitment, 0, 800)
    realized_gain = _pct(rng, commitment, 100, 1_200)
    income = Decimal(rng.randint(0, 50_000_00)) / 100
    issue, due = _dates(rng, 0, 10)
    return DistributionNotice(
        fund_name=rng.choice(FUND_NAMES),
        investor_name=rng.choice(INVESTOR_NAMES),
        issue_date=issue,
        due_date=due,
        currency=rng.choice(CURRENCIES),
        commitment=commitment,
        # Simplification: a distribution leaves the unfunded commitment as it was.
        unfunded_commitment_before=unfunded,
        unfunded_commitment_after=unfunded,
        cumulative_contributions_before=contributed,
        cumulative_distributions_before=distributed,
        total_amount=return_of_capital + realized_gain + income,
        return_of_capital=return_of_capital,
        realized_gain=realized_gain,
        income=income,
    )


def make_invoice(rng: random.Random) -> Invoice:
    vendor = rng.choice(sorted(VENDORS))
    services = VENDORS[vendor]
    items = []
    for description in rng.sample(services, rng.randint(1, len(services))):
        quantity = Decimal(rng.randint(1, 40))
        unit_price = Decimal(rng.randint(150_00, 950_00)) / 100
        items.append(
            LineItem(
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                amount=quantity * unit_price,
            )
        )
    subtotal = sum((item.amount for item in items if item.amount is not None), Decimal("0.00"))
    tax_rate = Decimal(rng.choice((0, 5, 20)))
    tax = (subtotal * tax_rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    issue, due = _dates(rng, 30, 30)
    return Invoice(
        vendor_name=vendor,
        bill_to=rng.choice(FUND_NAMES),
        invoice_number=f"{vendor[:3].upper()}-{rng.randint(1000, 9999)}",
        issue_date=issue,
        due_date=due,
        currency=rng.choice(CURRENCIES),
        line_items=items,
        subtotal=subtotal,
        tax=tax,
        total=subtotal + tax,
    )


MAKERS: dict[DocType, Callable[[random.Random], ExtractedFields]] = {
    DocType.CAPITAL_CALL: make_capital_call,
    DocType.DISTRIBUTION: make_distribution,
    DocType.INVOICE: make_invoice,
}


Notice = CapitalCallNotice | DistributionNotice


def plant_error(rng: random.Random, fields: Notice, kind: ErrorKind) -> tuple[Notice, PlantedError]:
    """Move one number so the notice no longer adds up, and record what changed."""
    field_name = "total_amount" if kind == "split_total_mismatch" else "unfunded_commitment_after"
    delta = Decimal(rng.choice(("1000.00", "10000.00", "-1000.00", "90.00")))
    wrong = shift_field(fields, field_name, delta)
    error = PlantedError(
        kind=kind,
        field=field_name,
        correct_value=getattr(fields, field_name),
        printed_value=getattr(wrong, field_name),
    )
    return wrong, error


def build_split(rng: random.Random, split: str, per_type: int, planted: int) -> list[AnswerFile]:
    """Build one split, with types shuffled so file names never reveal the type."""
    slots = [(doc_type, i) for doc_type in DocType for i in range(per_type)]
    rng.shuffle(slots)

    # Pick which notices get a planted error: the same number of calls and
    # distributions, alternating the two kinds of mistake.
    error_slots: dict[tuple[DocType, int], ErrorKind] = {}
    for doc_type in (DocType.CAPITAL_CALL, DocType.DISTRIBUTION):
        for n, i in enumerate(rng.sample(range(per_type), planted)):
            error_kind: ErrorKind = (
                "split_total_mismatch" if n % 2 == 0 else "unfunded_after_mismatch"
            )
            error_slots[(doc_type, i)] = error_kind

    answers = []
    for number, (doc_type, i) in enumerate(slots, start=1):
        fields: ExtractedFields = MAKERS[doc_type](rng)
        error = None
        kind = error_slots.get((doc_type, i))
        if kind is not None and isinstance(fields, Notice):
            fields, error = plant_error(rng, fields, kind)
        # Hard case: every fifth document of a type has no title at all.
        title = None if i % 5 == 4 else rng.choice(TITLES[doc_type])
        answers.append(
            AnswerFile(
                doc_id=f"{split}_{number:03d}",
                split="train" if split == "train" else "test",
                doc_type=doc_type,
                layout=rng.randrange(3),
                title=title,
                fields=fields,
                planted_error=error,
            )
        )
    return answers


def build_dataset(seed: int = SEED) -> tuple[list[AnswerFile], list[AnswerFile]]:
    """Return (train, test). The same seed always gives the same documents."""
    rng = random.Random(seed)
    train = build_split(rng, "train", TRAIN_PER_TYPE, planted=0)
    test = build_split(rng, "test", TEST_PER_TYPE, planted=PLANTED_PER_NOTICE_TYPE)
    return train, test
