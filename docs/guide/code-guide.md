---
type: guide
purpose: A walk through the code, module by module, so Kshitij can explain every line.
owner: Kshitij
reviewed: 2026-10-12
---

# Code guide

Read this with the code open next to it. Each section names a file, says what it does, and says why it is built that way.

## The big picture

The tool takes a PDF from a fund administrator's inbox and answers three questions. What kind of document is it? What does it say? Do its numbers add up?

```
data generation (done)          the pipeline (partly done)
--------------------            --------------------------
synth.py   true values          pdftext.py   PDF to text
render.py  values to PDF        (classifier, not built yet)
generate.py write to disk       extract.py   text to typed fields, with the LLM
                                checks.py    do the numbers add up?
                                score.py     compare with the answer file
                                compare.py   try models on train documents
```

Everything is synthetic. We build fake documents and keep the true answer for each one, so we can measure how well the pipeline does.

## Suggested reading order

1. `schema.py`, because every other file uses its models.
2. `synth.py`, then `render.py`, then `generate.py`.
3. `pdftext.py`, `llm.py`, `extract.py`.
4. `checks.py`, `score.py`, `compare.py`.
5. The tests, which show how each piece is meant to behave.

## schema.py: the shapes of the data

This file defines the Pydantic models. A model is a class that says which fields exist and what type each one has.

1. `DocType` lists the three document types. It is a `StrEnum`, so each value is also a plain string such as `"capital_call"`.
2. `_Strict` is the base class. `extra="forbid"` makes an unknown key an error. A typo like `totl_amount` fails loudly instead of being dropped.
3. `NoticeBase` holds the fields every notice shares. `CapitalCallNotice` and `DistributionNotice` add their own split fields.
4. `Invoice` and `LineItem` describe a bill.
5. Every field defaults to `None`. A document may not show a field, and the extractor must be able to say "not shown".
6. `MODEL_FOR_TYPE` maps each type to its model. Extraction uses it to pick the right schema.
7. `AnswerFile` is the truth for one generated PDF. Its validator `_parse_fields_by_type` uses `doc_type` to pick the model for `fields`. Without it, a notice with only shared fields would fit both notice models and Pydantic would have to guess.

Key idea: the schema checks types only, never business rules. If it rejected "parts do not add up to the total", the retry would push the model to change numbers until they add up. That would hide the exact mistakes we want to catch. See decision 4.

## synth.py: deciding what each document says

This file builds the true values. It never draws anything.

1. `SEED` fixes the random numbers, so every run builds the same documents.
2. `_pct` takes a random share of an amount in basis points (1 basis point is 0.01%) and rounds to the cent with `ROUND_HALF_UP`, the rounding people expect on money.
3. `_account` makes the investor's history: commitment, paid in so far, and received so far.
4. `make_capital_call`, `make_distribution`, and `make_invoice` build one clean document each. Clean means every rule holds. For a call, unfunded after is unfunded before minus the call.
5. `shift_field` returns a copy of a notice with one money field moved. It uses `model_copy`, so the original stays unchanged. You wrote this one.
6. `plant_error` uses `shift_field` to break one rule on purpose, and records the correct and printed values in a `PlantedError`.
7. `build_split` shuffles the types so file names never give the type away, picks which notices get an error, and drops the title on every fifth document of a type. Those untitled documents are the hard cases for the classifier.
8. `build_dataset` builds train first, then test, from one random generator. The order matters. Changing it would change every document.

## render.py: turning values into a PDF

1. `Style` picks the look of one document once: date format, money format, and labels. Every line in that document then uses the same look, as a real one would.
2. `LABELS` gives several names for the same field, such as "Amount of This Drawdown" for `total_amount`. This is what makes extraction a real task and not a simple lookup.
3. `NoticePDF.footer` prints the synthetic label on every page.
4. `_render_notice` draws a notice in one of 3 layouts. Layout 0 is one table with everything. Layout 1 is a letter with the total inside a sentence. Layout 2 is a statement in two sections with the total first.
5. `_render_invoice` also has 3 layouts. Layout 0 is a table with quantity and unit price columns. Layout 1 writes each line as hours at a rate. Layout 2 puts quantity times unit price inside the row label.
6. `_filler` adds 3 lines of boilerplate. The late payment warning only goes on capital calls, since only a call asks the investor to pay.
7. `render_pdf` seeds its own random generator from the document id. So a document always looks the same, and changing one document's look never changes another's.

## generate.py: writing the data set

`python -m fund_notices.generate` writes one PDF and one JSON answer file per document into `data/train` and `data/test`. It deletes old files first, so nothing stale is left. It then copies two documents into `samples/`, one clean and one with a planted error. `data/` is git ignored. `samples/` is committed. See decision 8.

## pdftext.py: reading a PDF

`pdf_text` uses pypdf to pull the text from every page. Every later step works on this text, not on the PDF itself.

## llm.py: the one door to the model

1. `LLMClient` is a `Protocol`. It says what any client must offer: a `name` and a `complete_json` method. A class does not have to inherit from it. If it has those two members, it fits. This is how the tests swap in a fake model.
2. `OllamaClient` is the real one. It sends the JSON schema in Ollama's `format` parameter. Ollama then only lets the model write JSON that fits the schema. Temperature 0 makes the model pick its most likely answer each time.
3. `model_from_env` reads the model name from `FUND_NOTICES_MODEL`. No model name is written into the code.
4. `CachedClient` wraps any client. It hashes the model name, prompts, and schema with SHA 256 and uses the hash as a file name in `cache/`. Same request, same file, no model call. It counts `model_calls` and `cache_hits`, which the evaluate command will report. See decision 6.

Why this shape: the rest of the code only knows `LLMClient`. A cloud model later means one new class, and nothing else changes. See decision 7.

## extract.py: from text to typed fields

The flow for one document:

1. `build_prompt` writes the document type, a hint for each field, and the text.
2. `SYSTEM` holds the rules. Rule 1 is the important one: copy what the page says, even when it looks wrong.
3. `numbers_only` edits the schema before it goes to Ollama. Pydantic lets a `Decimal` be a number or a string. A string lets the model write `"106,473.60 EUR"`, which then fails. Removing the string choice blocks that mistake before it happens.
4. `extract` asks the model, then checks the reply with `model_validate_json`. If that fails, it asks once more and shows the model its last reply and the error. If the second reply also fails, it returns `fields=None` and the error. That document then goes to a person.

`ExtractionResult` records the fields, how many attempts it took, and the error if any.

## checks.py: do the numbers add up?

Each document type has its rules.

| Type | Check | Rule |
|---|---|---|
| Capital call | `split_total` | investments + management fee + expenses = total |
| Capital call | `unfunded_after` | unfunded after + total = unfunded before |
| Capital call | `unfunded_before` | unfunded before + paid in = commitment |
| Distribution | `split_total` | return of capital + realized gain + income = total |
| Distribution | `unfunded_after` | unfunded after = unfunded before |
| Distribution | `unfunded_before` | unfunded before + paid in = commitment |
| Invoice | `line_amount` | quantity x unit price = amount, for each line |
| Invoice | `subtotal` | the line amounts add up to the subtotal |
| Invoice | `total` | subtotal + tax = total |

Three points to know:

1. `_sum_rule` does the work for most checks: the parts must add up to the total.
2. A missing number is a `Problem`, not a pass. A check that cannot run has not shown the document is fine.
3. Sums are exact `Decimal` sums, so there is no rounding tolerance. With floats this would not work. See decision 5.

One wrong number can break more than one rule. A wrong total on a capital call breaks `split_total` and also `unfunded_after`, because both use the total.

## score.py: how right was the extraction?

`field_matches` compares each field of the answer file with what was extracted, and returns true or false per field. Money compares by value, so `100.5` matches `100.50`. Text is trimmed first. All the line items count as one field. A failed extraction gets every field wrong.

## compare.py: choosing a model

`python -m fund_notices.compare qwen3:4b llama3.2:3b` runs extraction on a few train documents with each model and prints fields right, documents fully right, failed extractions, model calls, cache hits, and run time. It only uses train documents, so the test set stays unseen. See decision 3.

## The tests

Tests never call Ollama. They use small fake clients defined in the test files.

| File | What it protects |
|---|---|
| `test_schema.py` | Money parses to exact Decimal, a wrong document still parses, bad types and unknown keys are rejected, and JSON round trips keep values exact. |
| `test_synth.py` | Split sizes, clean documents add up, planted errors break one rule, same seed same data. |
| `test_render.py` | Synthetic label on every page, every value printed, titles dropped when they should be. |
| `test_llm.py` | The cache saves calls and its key covers everything that changes the answer. |
| `test_extract.py` | Good replies pass, bad ones retry once with the error, wrong numbers are kept as printed. |
| `test_checks.py` | Clean documents pass, every planted error is caught, a missing number is flagged. |
| `test_docs_check.py` | The docs rules in `scripts/docs_check.py`. |

`conftest.py` builds the data set once per test run and shares it, since building it takes a moment.

## Not built yet

1. The classifier. For now, extraction is told the true type from the answer file.
2. Embeddings and retrieval of similar train documents.
3. The evaluate command that runs the whole pipeline on the test set and reports scores.
