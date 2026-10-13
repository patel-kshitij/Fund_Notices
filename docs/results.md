---
type: results
purpose: Scores from the last evaluate run. Written by the evaluate command, never by hand.
owner: Kshitij
reviewed: 2026-10-13
---

# Results

Written by `python -m fund_notices.evaluate` on 2026-10-13. Model: `qwen3:4b`.
The test set has 45 documents. None of them was used for training or retrieval.

## Classification

| Measure | Result |
|---|---|
| Type right, all documents | 45/45 (100.0%) |
| Type right, untitled documents | 9/9 (100.0%) |
| MiniLM nearest neighbour right | 45/45 (100.0%) |
| Classifier and nearest neighbour disagree | 0 |

## Extraction, checks, and review

The design shows the model a worked example: the most similar train document
of the predicted type, with its answer. The last column leaves the example out.

| Measure | With worked example | Without |
|---|---|---|
| Fields right, all documents | 570/570 (100.0%) | 561/570 (98.4%) |
| Fields right, capital_call | 210/210 (100.0%) | 210/210 (100.0%) |
| Fields right, distribution | 210/210 (100.0%) | 209/210 (99.5%) |
| Fields right, invoice | 150/150 (100.0%) | 142/150 (94.7%) |
| Documents with every field right | 45/45 (100.0%) | 37/45 (82.2%) |
| Amounts wrong, in money fields and line items | 0 | 0 |
| Failed extractions | 0 | 0 |
| Documents that needed the retry | 0 | 0 |
| Planted errors caught by the math checks | 6/6 (100.0%) | 6/6 (100.0%) |
| Clean documents flagged by the math checks | 0/39 (0.0%) | 0/39 (0.0%) |
| Documents sent to a person | 6/45 (13.3%) | 6/45 (13.3%) |
| Model replies used | 45 | 45 |
| New model calls in this run | 0 | 0 |
| Model time, minutes | 16.6 | 17.7 |
| Model time per document, seconds | 22.1 | 23.6 |
| Run time of this run, minutes | 0.0 | 0.0 |

## Documents sent to a person

From the run with a worked example.

| Document | True type | Planted error | Reasons |
|---|---|---|---|
| `test_013` | `capital_call` | `unfunded_after_mismatch` | unfunded_after: unfunded_commitment_after + total_amount = 417300.00, but unfunded_commitment_before is 416300 |
| `test_024` | `distribution` | `split_total_mismatch` | split_total: return_of_capital + realized_gain + income = 2688267.3, but total_amount is 2698267.3 |
| `test_027` | `distribution` | `unfunded_after_mismatch` | unfunded_after: unfunded_commitment_after = 3722715, but unfunded_commitment_before is 3722625 |
| `test_028` | `capital_call` | `split_total_mismatch` | split_total: investments + management_fee + partnership_expenses = 551271.46, but total_amount is 551361.46; unfunded_after: unfunded_commitment_after + total_amount = 3333790.00, but unfunded_commitment_before is 3333700 |
| `test_033` | `capital_call` | `split_total_mismatch` | split_total: investments + management_fee + partnership_expenses = 52173.28, but total_amount is 52263.28; unfunded_after: unfunded_commitment_after + total_amount = 4407590.00, but unfunded_commitment_before is 4407500 |
| `test_039` | `distribution` | `split_total_mismatch` | split_total: return_of_capital + realized_gain + income = 1285103.55, but total_amount is 1286103.55 |

## Documents with a field extracted wrong

From the run with a worked example.

None.

From the run without a worked example.

| Document | True type | Wrong fields |
|---|---|---|
| `test_009` | `distribution` | fund_name |
| `test_012` | `invoice` | line_items |
| `test_015` | `invoice` | line_items |
| `test_019` | `invoice` | invoice_number, line_items |
| `test_021` | `invoice` | bill_to |
| `test_023` | `invoice` | line_items |
| `test_036` | `invoice` | line_items |
| `test_043` | `invoice` | invoice_number |
