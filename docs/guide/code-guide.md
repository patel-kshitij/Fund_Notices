---
type: guide
purpose: A walk through the code, module by module, so Kshitij can explain every line.
owner: Kshitij
reviewed: 2026-10-13
---

# Code guide

Read this with the code open next to it. Each section names a file, says what it does, and says why it is built that way.

## The big picture

The tool takes a PDF from a fund administrator's inbox and answers three questions. What kind of document is it? What does it say? Do its numbers add up?

```
data generation                 the pipeline, one document at a time
---------------                 ------------------------------------
synth.py    true values         pdftext.py   PDF to text
render.py   values to PDF       classify.py  text to type
generate.py write to disk       retrieve.py  second opinion on the type, and a worked example
                                extract.py   text to typed fields, with the LLM
                                checks.py    do the numbers add up?
                                pipeline.py  all of the above, plus the review decision

measuring                       commands
---------                       --------
score.py    field by field      generate.py  build the data set
compare.py  choose a model      evaluate.py  score the test set, write docs/results.md
                                process.py   read one PDF and print what it found
                                app.py       the same, as a web page for demos
```

Everything is synthetic. We build fake documents and keep the true answer for each one, so we can measure how well the pipeline does.

## Suggested reading order

1. `schema.py`, because every other file uses its models.
2. `synth.py`, then `render.py`, then `generate.py`.
3. `pdftext.py`, `classify.py`, `llm.py`, `extract.py`, `retrieve.py`.
4. `checks.py`, `pipeline.py`.
5. `score.py`, `compare.py`, `evaluate.py`, `process.py`.
6. `demo.py`, then `app.py`.
7. The tests, which show how each piece is meant to behave.

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

## classify.py: what kind of document is it?

This is the baseline classifier. Later ideas must beat it to earn their place.

1. TF-IDF turns each text into word scores. A word scores high when it is frequent in this document and rare across the others. `ngram_range=(1, 2)` scores single words and pairs, so "capital call" counts as well as "call".
2. `WORDS_ONLY` keeps words of 2 or more letters and drops numbers. Amounts, dates, and references are random, so they say nothing about the type.
3. Logistic regression learns a weight per word for each type, and turns the sums into probabilities that add up to 1.
4. `train_classifier` refuses any test document, so decision 3 is enforced by the code and not only by habit.
5. `predict` returns the most likely type and its probability. `predict_proba` takes a list of texts and returns one row per text, so it gets `[text]` and takes row `[0]`. `argmax` gives the position of the top probability. That position picks the name from `classes_` and the value from the row. You wrote this one.

The probability is not the chance of being right. A model trained on 42 documents with default settings can be right while giving a modest probability. A threshold for sending a document to a person must be set from evaluation results, not assumed.

## llm.py: the one door to the model

1. `LLMClient` is a `Protocol`. It says what any client must offer: a `name` and a `complete_json` method. A class does not have to inherit from it. If it has those two members, it fits. This is how the tests swap in a fake model.
2. `OllamaClient` is the real one. It sends the JSON schema in Ollama's `format` parameter. Ollama then only lets the model write JSON that fits the schema. Temperature 0 makes the model pick its most likely answer each time. `think=False` stops qwen3 from writing hidden reasoning first, which made it very slow. See decision 16. `num_ctx` sets how many tokens the model can see. A prompt with a worked example is long, and if it did not fit, Ollama would silently cut the start of the prompt, where the rules are.
3. `model_from_env` reads the model name from `FUND_NOTICES_MODEL`. No model name is written into the code.
4. `CachedClient` wraps any client. It hashes the model name, prompts, and schema with SHA 256 and uses the hash as a file name in `cache/`. Same request, same file, no model call. Each file holds the reply and how many seconds the model took. It counts `model_calls`, `cache_hits`, and `model_seconds`, so a rerun from the cache still reports the real model time. See decisions 6 and 20.

Why this shape: the rest of the code only knows `LLMClient`. A cloud model later means one new class, and nothing else changes. See decision 7.

## extract.py: from text to typed fields

The flow for one document:

1. `build_prompt` writes the document type, a hint for each field, and the text. When it gets an `Example`, it puts a worked example before the text: a similar train document and its true answer. The prompt says the example shows the format only, so the model takes values from the real text.
2. `SYSTEM` holds the rules. Rule 1 is the important one: copy what the page says, even when it looks wrong.
3. `numbers_only` edits the schema before it goes to Ollama. Pydantic lets a `Decimal` be a number or a string. A string lets the model write `"106,473.60 EUR"`, which then fails. Removing the string choice blocks that mistake before it happens.
4. `require_every_key` edits the schema again so every key is required. Our models give every field a default, so without this the model skips keys it is unsure of. A value can still be null. `model_schema` applies both edits.
5. `extract` asks the model, then checks the reply with `model_validate_json`. If that fails, it asks once more and shows the model its last reply and the error. If the second reply also fails, it returns `fields=None` and the error. That document then goes to a person.

`ExtractionResult` records the fields, how many attempts it took, and the error if any.

`answer_json` writes the worked example's answer as JSON. It exists because `json.dumps` cannot write a `Decimal`. Turning money into a float could change its digits, and turning it into a string would put it in quotes, which rule 2 forbids. So each `Decimal` is written as its own digits.

## retrieve.py: finding similar train documents

`TrainPool` holds the train documents and compares a new document with them in two ways.

1. `nearest_type` uses MiniLM embeddings. An embedding is a list of 384 numbers that stands for the meaning of a text. Texts with similar meaning get similar lists. The type of the closest train document is a second opinion on the classifier. MiniLM looks at the text in a different way from TF-IDF, so when the two disagree, the document is worth a look.
2. `example` uses the classifier's own TF-IDF word scores. It picks the train document of the predicted type with the most similar words. On the train set, this matched the page layout far more often than MiniLM did, and the layout is what the example needs to show. A train document is never its own example, because that would hand the model the answer.
3. Both use cosine similarity. Each row of numbers has length 1, so a dot product between two rows is their cosine: 1 means the same direction, lower means less alike.
4. `minilm_embedder` loads MiniLM from `cache/models` inside the project. Only the first run downloads it. After that it loads without the internet.

The pool refuses test documents, like the classifier. See decisions 3 and 18.

## pipeline.py: one document, start to finish

`NoticeReader.read` runs every step on one text: classify, get the second opinion, pick the worked example, extract, and run the math checks. It returns an `Outcome`.

A document goes to a person when any of these is true:

1. The classifier and the MiniLM nearest neighbour disagree on the type.
2. Extraction failed twice.
3. A math check found a problem, including a number it needed but could not find.

There is no confidence threshold. On the train set, the classifier's probabilities were low even when it was right, so any cutoff would have been a guess. Disagreement between two different methods needs no tuning. See decision 19.

`load_split` reads every PDF and answer file in a folder. `from_train` builds the classifier and pool from train documents in one step.

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

`amounts_wrong` counts only the numbers: money fields and the quantity, unit price, and amount of each line item. A wrong amount is the costly mistake, because it can make a correct notice fail the checks or a wrong one pass. A wrong name is only untidy.

## compare.py: choosing a model

`python -m fund_notices.compare qwen3:4b llama3.2:3b` runs extraction on a few train documents with each model and prints fields right, documents fully right, failed extractions, model calls, cache hits, and run time. It only uses train documents, so the test set stays unseen. It tells extraction the true type and shows no worked example, because it only compares models. See decisions 3 and 15.

## evaluate.py: the numbers for the README

`python -m fund_notices.evaluate` runs the whole pipeline on all 45 test documents, twice. The first run shows the model a worked example, which is the design. The second leaves it out, so we can see what the example adds. It writes `docs/results.md`.

1. `run` reads every document and keeps one row of facts per document in a pandas `DataFrame`: the true and predicted type, how many fields were right, whether a planted error was caught, and whether the document went to a person.
2. `classification_rows` and `run_rows` turn those rows into the measures in the results tables. pandas makes each one a short line, for example `rows["review"].sum()` counts the documents sent to a person.
3. `render` writes the results page, including every document sent to a person and every document with a wrong field, so nothing is hidden behind an average.

AGENTS.md says no number goes in the docs unless it came from this command. The command writes the page itself, so that rule holds by construction. See decision 20.

## process.py: one PDF from the command line

`python -m fund_notices.process samples/test_013.pdf` reads one PDF and prints the type, the second opinion, the worked example used, the fields, and whether it goes to a person and why. It is the quickest way to see the tool work.

## app.py and demo.py: the demo page

`streamlit run src/fund_notices/app.py` opens a page at `http://localhost:8501`. Pick a test document or upload a PDF, then press Read it. The PDF shows on the left. On the right are the review decision with its reasons, the type and the second opinion, and a table of fields. For a test document, each field is marked against the answer file. A second tab shows `docs/results.md`.

1. Streamlit runs the whole file again on every click. So `get_reader` is wrapped in `st.cache_resource`, which builds the classifier and loads MiniLM once, and the last result is kept in `st.session_state`, which survives the reruns.
2. Nothing is read until Read it is pressed, so opening the page never calls the model.
3. `demo.py` holds the plain functions: `show` writes a value for the page and keeps every digit of money, `field_rows` builds the field table, and `choice_label` marks the test documents with a planted error so a demo can show one being caught. They hold no Streamlit code, so the tests call them directly.
4. `.streamlit/config.toml` turns off Streamlit's usage statistics and serves the page on localhost only. See decision 22.

## The tests

Tests never call Ollama and never download MiniLM. They use small fakes defined in the test files: fake model clients, and `hash_embed`, which gives each text a fixed random direction in place of a real embedding.

| File | What it protects |
|---|---|
| `test_schema.py` | Money parses to exact Decimal, a wrong document still parses, bad types and unknown keys are rejected, and JSON round trips keep values exact. |
| `test_synth.py` | Split sizes, clean documents add up, planted errors break one rule, same seed same data. |
| `test_render.py` | Synthetic label on every page, every value printed, titles dropped when they should be. |
| `test_llm.py` | The cache saves calls, keeps the model time for reruns, and its key covers everything that changes the answer. |
| `test_classify.py` | Training refuses test documents, numbers are not features, training is repeatable, and `predict` returns the top type and its probability. |
| `test_extract.py` | Good replies pass, bad ones retry once with the error, wrong numbers are kept as printed, and the worked example shows exact money before the real text. |
| `test_retrieve.py` | The pool refuses test documents, the nearest type follows the closest document, and the example is the most similar train document of the asked type but never the document itself. |
| `test_checks.py` | Clean documents pass, every planted error is caught, a missing number is flagged. |
| `test_pipeline.py` | Each review reason on its own sends a document to a person, and a planted error read end to end is caught. |
| `test_evaluate.py` | The results measures count correctly, and the results page passes the docs check. |
| `test_demo.py` | Money on the page keeps every digit, fields are marked against the answer file, and the page loads without errors and without calling the model. |
| `test_docs_check.py` | The docs rules in `scripts/docs_check.py`. |

`conftest.py` builds the data set and reads the text of every PDF once per test run, and shares both, since that takes a moment.

## Known limits

1. The documents are synthetic, from one generator with 3 layouts per type. Real notices vary much more, so the scores say how well the method works on this data, not on a real inbox.
2. The system is fitted to the generator, though no test document leaked. The field hints in `extract.py` use the generator's own label words, for example "funding, payment, settlement, or value date" for `due_date`. The worked example also comes from the same generator.
3. The test set is small. One document is worth a lot of percentage points.
4. The model is a small local one, chosen to fit an 8 GB laptop. A larger model would likely make fewer mistakes, at more cost or time.
5. A document that goes to a person is only flagged. The tool does not say which number is wrong, only which rule failed.
