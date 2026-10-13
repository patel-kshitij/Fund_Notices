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

## 11. 42 train and 45 test documents

Decision: The train set has 42 documents, 14 of each type. The test set has 45, 15 of each type. This replaces the 15 train documents in the first plan.
Why: More train documents give the baseline more to learn from and retrieval more examples to choose from, at no cost, since generation takes seconds. The test set stays at 45 because a smaller one makes each document worth too much of the score. 42 is used instead of 40 so each type gets the same number.

## 12. Money in the model's schema must be a number

Decision: Before the schema goes to Ollama, every money field allows a JSON number or null, never a string.
Why: Pydantic lets a Decimal be a string. A string lets a small model copy "106,473.60 EUR" as printed, which then fails validation. A number only schema blocks that mistake before it happens, and Pydantic still reads the number into an exact Decimal.

## 13. A check that cannot run is a problem

Decision: When a math check needs a number that is missing, it reports a problem instead of passing.
Why: A check that did not run has not shown the document is fine. Treating it as a pass would let a notice with a missing total through without review.

## 14. Extraction before the classifier

Decision: Extraction and the math checks are built before the classifier. Until the classifier exists, extraction is given the true type from the answer file.
Why: Extraction and the checks are the core of the tool and the larger risk, so they come first. The cost is that early extraction scores assume a perfect classifier. Scores from the full pipeline will come only from the evaluate command.

## 15. The model is qwen3:4b

Decision: Extraction uses `qwen3:4b` through Ollama, set with `FUND_NOTICES_MODEL=qwen3:4b`. `llama3.2:3b` was the other option.
Why: Both were tried on a few train documents with `python -m fund_notices.compare`. qwen3 made a couple of mistakes in text fields. llama3.2 changed digits inside money fields and left out fields the page shows. A changed digit is the worse mistake, because it looks like a real number and makes a correct notice fail the math checks. qwen3 is slower, but the cache makes reruns free. The sample was small, so this choice does not stand in for a score.

## 16. No thinking, and every key required

Decision: Ollama is called with `think=False`. The schema sent to the model marks every key as required, while a value may still be null.
Why: With thinking on, qwen3 took several minutes on the first document. Without required keys, the model skipped fields such as the fund name and the dates, because every field in our models has a default.

## 17. The baseline classifier is TF-IDF and logistic regression on words

Decision: The classifier scores single words and pairs of words with TF-IDF, leaves numbers out, and uses logistic regression. It trains on train documents only and refuses a test document.
Why: It is fast, needs no model download, and each weight can be read and explained. Numbers are left out because amounts and dates are random in this data and would only add noise. It is the baseline that any later classifier must beat.

## 18. Two kinds of similarity, each where it works

Decision: MiniLM embeddings give a second opinion on the type: the type of the closest train document. TF-IDF word scores pick the worked example for extraction: the most similar train document of the predicted type, shown with its true answer. A train document is never its own example.
Why: Both were checked on the train set only. MiniLM's nearest document usually had the right type, and it looks at text in a different way from the TF-IDF classifier, so a disagreement means something. But among documents of one type, MiniLM's nearest shared the page layout about as often as chance, while TF-IDF's nearest shared it far more often. The example is there to show where fields sit on that kind of page, so it needs the layout. Using a document as its own example would hand the model the answer.

## 19. When a document goes to a person

Decision: A document goes to a person when the classifier and the MiniLM nearest neighbour disagree on the type, when extraction fails twice, or when any math check finds a problem, including a missing number. There is no confidence threshold.
Why: On the train set, the classifier's probabilities were low even when it was right, so any cutoff would have been a guess. Disagreement between two different methods needs no tuning. A math problem means the document is wrong or was read wrong, and either way a person should look.

## 20. The evaluate command writes the results page

Decision: `python -m fund_notices.evaluate` runs the pipeline on the test set twice, with and without the worked example, and writes `docs/results.md`. The README takes its numbers from that page. The cache stores the seconds each reply took, so a rerun from the cache reports the real model time. The design, with the worked example, was fixed before the first run on the test set.
Why: AGENTS.md says no number goes in the docs unless it came from the evaluate command. Writing the page from the command makes that hold by construction. The run without the example shows what retrieval adds. Fixing the design first means the test set judged it and did not choose it.

## 21. MiniLM lives in the project cache

Decision: MiniLM is downloaded once into `cache/models` inside the project, which is git ignored. After that it loads with `local_files_only`, without the internet.
Why: AGENTS.md says to install nothing globally, and the default download folder is global. Loading offline also matches the promise that the tool runs on the laptop alone. No document ever leaves the machine. Only the first download of the model uses the internet.

## 22. A Streamlit page for demos

Decision: `src/fund_notices/app.py` is a Streamlit page that reads one PDF at a time and shows the PDF next to what the tool found, with each field marked against the answer file. Kshitij approved Streamlit, with its `pdf` extra, as the one addition to the stack. The project config turns off Streamlit's usage statistics and serves the page on localhost only.
Why: A live page shows the tool far better than terminal output, and Streamlit keeps the page to a short Python file that can be explained line by line. By default Streamlit sends usage statistics, listens on every network interface, and looks up the public IP address online. Each of those breaks the promise that everything stays on the laptop, so the config turns them off. The logic lives in `demo.py` with plain functions, so tests do not need a browser.
