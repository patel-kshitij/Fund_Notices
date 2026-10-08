---
type: decisions
purpose: Numbered, append only log of project decisions and the reason for each.
owner: Kshitij
reviewed: 2026-10-08
---

# Decisions

Append only. To change a decision, add a new entry that replaces it and say which one.

## 1. Claude never runs git

Decision: Claude never runs git or touches GitHub. Kshitij reviews and commits every change.
Why: Kshitij must be able to explain every line in the repo. Reviewing each change before committing it is how that happens.

## 2. Synthetic data from the ILPA template

Decision: All documents are synthetic, built from the fields in ILPA's Capital Call and Distribution Notice Best Practices, Version 1.1 (2016). Every page says "SYNTHETIC SAMPLE, NOT A REAL NOTICE".
Why: Real notices are confidential. The ILPA template keeps the fields realistic, and the label stops anyone mistaking a sample for a real notice.

## 3. Fixed seed, separate train and test sets

Decision: The generator uses a fixed random seed. The train set is both the classifier's training data and the retrieval pool. Nothing from the test set is used for training or retrieval.
Why: A fixed seed makes every run repeatable. Keeping the test set apart is the only way the scores mean anything.

## 4. Extraction reports what the document says

Decision: The extractor copies what the document says, even when the document is wrong. Catching wrong numbers is the job of the math checks. The schema therefore checks types only, never business rules.
Why: If extraction "fixed" mistakes, the checks would never see them and a wrong notice would pass. If the schema enforced rules, the retry loop would push the model to change the numbers.

## 5. Money is Decimal

Decision: Every money value is a Python `Decimal`, never a `float`. Answer files store money as strings.
Why: Floats cannot hold most cents exactly, so sums drift and equality checks fail. Strings in JSON keep the exact value.

## 6. LLM responses are cached on disk

Decision: Each LLM response is cached on disk under a hash of the request. The cache is git ignored.
Why: Reruns are free and repeatable, and the evaluation gives the same numbers each time.

## 7. The LLM runs locally with Ollama

Decision: The LLM runs on the laptop with Ollama through the `ollama` Python package. There is no Anthropic API, no API key, and no `.env` file. The model name comes from an environment variable, and the LLM sits behind one small interface. Extraction uses Ollama structured outputs with the Pydantic JSON schema, then validates with Pydantic and retries once. The evaluate command reports model calls and run time instead of cost.
Why: There are no API credits for this project. A local model is free and no document leaves the machine, which also matches how a fund administrator thinks about client data. The small interface keeps a cloud model as a later option.

## 8. Commit only 2 sample documents

Decision: The full generated data set is git ignored. Two sample PDFs with their answer files are committed under `samples/`. Anyone can rebuild the full set with the generator.
Why: The repo stays small, and a visitor can still open a real example without running anything. The cost is that the scores depend on the generator rebuilding the exact same files, so the seed is fixed and fpdf2 is pinned to one version.

## 9. Python 3.12 managed by uv

Decision: The project `.venv` uses a Python 3.12 downloaded by uv. Nothing is installed with Homebrew or into the system Python.
Why: The laptop has Python 3.14, which the stack does not target. uv keeps its Python in its own cache and leaves the system alone.

## 10. Invoices get a full model with line items

Decision: Invoices are extracted with a full model: vendor, bill to, invoice number, dates, currency, line items (description, quantity, unit price, amount), subtotal, tax, and total.
Why: Invoices are the odd document type in a fund administrator's inbox, and a realistic one has line items. It also gives invoices their own math checks. The cost is more generator work and a harder schema for a small local model.
