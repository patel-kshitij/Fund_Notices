"""Math checks on extracted fields. They catch documents whose numbers do not add up.

Extraction copies what the page says, even when it is wrong. These checks are
where wrong numbers get caught. Each check returns a Problem when a rule fails,
or when a number it needs is missing, because a check that cannot run is not a pass.
All sums are exact Decimal sums, so no rounding tolerance is needed.
See docs/DECISIONS.md, entry 4.
"""

from dataclasses import dataclass
from decimal import Decimal

from fund_notices.schema import CapitalCallNotice, DistributionNotice, ExtractedFields, Invoice


@dataclass(frozen=True)
class Problem:
    check: str
    detail: str


def _sum_rule(
    check: str, parts: dict[str, Decimal | None], total_name: str, total: Decimal | None
) -> list[Problem]:
    """The named parts must add up to the total."""
    missing = [name for name, value in parts.items() if value is None]
    if total is None:
        missing.append(total_name)
    if missing:
        return [Problem(check, f"cannot check, missing {', '.join(missing)}")]
    found = sum((v for v in parts.values() if v is not None), Decimal(0))
    if found != total:
        return [Problem(check, f"{' + '.join(parts)} = {found}, but {total_name} is {total}")]
    return []


def check_capital_call(f: CapitalCallNotice) -> list[Problem]:
    split = {
        "investments": f.investments,
        "management_fee": f.management_fee,
        "partnership_expenses": f.partnership_expenses,
    }
    # Unfunded after = unfunded before minus this call, so before = after + call.
    unfunded = {
        "unfunded_commitment_after": f.unfunded_commitment_after,
        "total_amount": f.total_amount,
    }
    # Unfunded before = commitment minus what was paid in, so commitment = unfunded + paid in.
    paid_in = {
        "unfunded_commitment_before": f.unfunded_commitment_before,
        "cumulative_contributions_before": f.cumulative_contributions_before,
    }
    return [
        *_sum_rule("split_total", split, "total_amount", f.total_amount),
        *_sum_rule(
            "unfunded_after", unfunded, "unfunded_commitment_before", f.unfunded_commitment_before
        ),
        *_sum_rule("unfunded_before", paid_in, "commitment", f.commitment),
    ]


def check_distribution(f: DistributionNotice) -> list[Problem]:
    split = {
        "return_of_capital": f.return_of_capital,
        "realized_gain": f.realized_gain,
        "income": f.income,
    }
    # A distribution pays money out, so it leaves the unfunded commitment as it was.
    unchanged = {"unfunded_commitment_after": f.unfunded_commitment_after}
    paid_in = {
        "unfunded_commitment_before": f.unfunded_commitment_before,
        "cumulative_contributions_before": f.cumulative_contributions_before,
    }
    return [
        *_sum_rule("split_total", split, "total_amount", f.total_amount),
        *_sum_rule(
            "unfunded_after", unchanged, "unfunded_commitment_before", f.unfunded_commitment_before
        ),
        *_sum_rule("unfunded_before", paid_in, "commitment", f.commitment),
    ]


def check_invoice(f: Invoice) -> list[Problem]:
    problems: list[Problem] = []
    if not f.line_items:
        problems.append(Problem("line_items", "cannot check, no line items"))
    for n, item in enumerate(f.line_items, start=1):
        if item.quantity is None or item.unit_price is None or item.amount is None:
            problems.append(Problem("line_amount", f"cannot check line {n}, a number is missing"))
        elif item.quantity * item.unit_price != item.amount:
            problems.append(
                Problem(
                    "line_amount",
                    f"line {n}: {item.quantity} x {item.unit_price} is not {item.amount}",
                )
            )
    lines = {f"line {n}": item.amount for n, item in enumerate(f.line_items, start=1)}
    problems += _sum_rule("subtotal", lines, "subtotal", f.subtotal)
    problems += _sum_rule("total", {"subtotal": f.subtotal, "tax": f.tax}, "total", f.total)
    return problems


def check(fields: ExtractedFields) -> list[Problem]:
    """Run every math check for this type. An empty list means the numbers add up."""
    if isinstance(fields, CapitalCallNotice):
        return check_capital_call(fields)
    if isinstance(fields, DistributionNotice):
        return check_distribution(fields)
    return check_invoice(fields)
