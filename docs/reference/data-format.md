---
type: reference
purpose: The only home for field definitions and the answer file format.
owner: Kshitij
reviewed: 2026-10-08
---

# Data format

The code that matches this page lives in `src/fund_notices/schema.py`.

## Document types

| Value | Meaning |
|---|---|
| `capital_call` | A notice asking the investor to pay money into the fund. |
| `distribution` | A notice telling the investor the fund is paying money out. |
| `invoice` | A bill from a service provider to the fund. The odd one out. |

## Value types

1. Money is a decimal number. In JSON it is a string, for example `"125000.00"`.
2. Dates are ISO dates, for example `"2026-03-15"`.
3. Currency is the code the document prints, for example `"USD"`.
4. Any field may be `null` when the document does not show it.
5. The schema checks types only. Rules such as "the split adds up to the total" belong to the math checks.

## Shared notice fields (capital calls and distributions)

These come from ILPA's Capital Call and Distribution Notice Best Practices, Version 1.1 (2016). "LP" means the limited partner, the investor who receives the notice.

| Field | Type | Meaning |
|---|---|---|
| `fund_name` | text | The fund that sends the notice. |
| `investor_name` | text | The LP the notice is addressed to. |
| `issue_date` | date | The date the notice was issued. |
| `due_date` | date | The date money must arrive or will be paid. Also called settlement or payment date. |
| `currency` | text | The currency of all amounts on the notice. |
| `commitment` | money | The LP's total commitment to the fund. |
| `unfunded_commitment_before` | money | The LP's unfunded commitment before this notice. |
| `unfunded_commitment_after` | money | The LP's unfunded commitment after this notice. |
| `cumulative_contributions_before` | money | All the LP has paid in before this notice. |
| `cumulative_distributions_before` | money | All the LP has received before this notice. |
| `total_amount` | money | The LP's amount for this notice. |

## Capital call split

| Field | Type | Meaning |
|---|---|---|
| `investments` | money | The part of the call used to buy investments. |
| `management_fee` | money | The part of the call that pays the manager's fee. |
| `partnership_expenses` | money | The part of the call that pays fund expenses. |

## Distribution split

| Field | Type | Meaning |
|---|---|---|
| `return_of_capital` | money | Money returned from what the LP paid in. |
| `realized_gain` | money | Profit from sold investments. |
| `income` | money | Interest and dividends. |

## Invoice fields

| Field | Type | Meaning |
|---|---|---|
| `vendor_name` | text | The company that sends the invoice. |
| `bill_to` | text | The fund or company the invoice is addressed to. |
| `invoice_number` | text | The vendor's reference for this invoice. |
| `issue_date` | date | The invoice date. |
| `due_date` | date | The date payment is due. |
| `currency` | text | The currency of all amounts. |
| `line_items` | list | Each line has `description` (text), `quantity` (decimal), `unit_price` (money), and `amount` (money). |
| `subtotal` | money | The sum before tax. |
| `tax` | money | The tax charged. |
| `total` | money | The amount to pay. |

## Answer file

Each generated PDF gets a JSON answer file with the same name. The exact layout is finalized in Day 1, Block 2, and this section will be updated then.
