"""Pull typed fields out of a document's text with the LLM.

The flow for one document:
1. Build a prompt with the rules, the fields for this type, and the text.
2. Ask the LLM for JSON that fits the type's Pydantic schema.
3. Check the reply with Pydantic. If it fails, ask once more and show the error.
4. If the second reply also fails, give up and return the error, so the
   document goes to a person instead of the pipeline guessing.
See docs/DECISIONS.md, entries 4 and 7.
"""

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from fund_notices.llm import LLMClient
from fund_notices.schema import MODEL_FOR_TYPE, DocType, ExtractedFields

MAX_ATTEMPTS = 2

SYSTEM = """You copy fields from a financial document into JSON.
Rules:
1. Copy what the document says, even if a number looks wrong. Never fix or recompute a value.
2. Write money as a plain number with no commas or currency code, for example 106473.60.
3. Write dates as YYYY-MM-DD.
4. Write currency as the three letter code the document shows, for example USD.
5. Use null for any field the document does not show."""

# Plain hints for each field. Documents use many labels for the same thing,
# so the hint lists the common ones.
NOTICE_HINTS = {
    "fund_name": "the fund that sends the notice",
    "investor_name": "the investor the notice is addressed to",
    "issue_date": "the date of the notice",
    "due_date": "the funding, payment, settlement, or value date",
    "currency": "the currency code",
    "commitment": "the investor's total commitment",
    "unfunded_commitment_before": "unfunded or remaining commitment before this notice",
    "unfunded_commitment_after": "unfunded or remaining commitment after this notice",
    "cumulative_contributions_before": "capital contributed or paid in to date",
    "cumulative_distributions_before": "distributions received to date",
    "total_amount": "the total amount of this notice",
}
CALL_HINTS = {
    "investments": "the part of the call for investments",
    "management_fee": "the part of the call for the management fee",
    "partnership_expenses": "the part of the call for fund or partnership expenses",
}
DISTRIBUTION_HINTS = {
    "return_of_capital": "return of capital",
    "realized_gain": "realized gain",
    "income": "income, dividends, or interest",
}
INVOICE_HINTS = {
    "vendor_name": "the company that sends the invoice",
    "bill_to": "who the invoice is addressed to",
    "invoice_number": "the invoice number",
    "issue_date": "the invoice date",
    "due_date": "the payment due date",
    "currency": "the currency code",
    "line_items": "one entry per line: description, quantity, unit_price, amount",
    "subtotal": "the sum before tax",
    "tax": "the tax charged",
    "total": "the total to pay",
}
HINTS = {
    DocType.CAPITAL_CALL: NOTICE_HINTS | CALL_HINTS,
    DocType.DISTRIBUTION: NOTICE_HINTS | DISTRIBUTION_HINTS,
    DocType.INVOICE: INVOICE_HINTS,
}


@dataclass
class ExtractionResult:
    fields: ExtractedFields | None
    attempts: int
    error: str | None = None


def numbers_only(schema: Any) -> Any:
    """Return a copy of a JSON schema where money must be a JSON number.

    Pydantic lets a Decimal be a number or a string. A string lets the model write
    "106,473.60 EUR", which then fails. Removing the string choice stops that early.
    """
    if isinstance(schema, list):
        return [numbers_only(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    result = {key: numbers_only(value) for key, value in schema.items()}
    choices = result.get("anyOf")
    if isinstance(choices, list) and {"type": "number"} in choices:
        result["anyOf"] = [c for c in choices if c != {"type": "string"}]
    return result


def build_prompt(text: str, doc_type: DocType) -> str:
    hints = "\n".join(f"- {name}: {hint}" for name, hint in HINTS[doc_type].items())
    return f"Document type: {doc_type}\n\nFields:\n{hints}\n\nDocument text:\n{text}"


def extract(text: str, doc_type: DocType, client: LLMClient) -> ExtractionResult:
    """Ask the LLM for the fields of one document, with one retry on a bad reply."""
    model = MODEL_FOR_TYPE[doc_type]
    schema = numbers_only(model.model_json_schema())
    prompt = build_prompt(text, doc_type)
    error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        reply = client.complete_json(SYSTEM, prompt, schema)
        try:
            return ExtractionResult(fields=model.model_validate_json(reply), attempts=attempt)
        except ValidationError as exc:
            error = str(exc)
            prompt = (
                f"{build_prompt(text, doc_type)}\n\nYour last reply was:\n{reply}\n\n"
                f"It was rejected because:\n{error}\n\nReply again with JSON that fixes this."
            )
    return ExtractionResult(fields=None, attempts=MAX_ATTEMPTS, error=error)
