---
type: readme
purpose: One screen for a visitor. What the tool does and how to run it.
owner: Kshitij
reviewed: 2026-10-13
---

# fund-notices

A fund administrator's inbox fills with capital call notices, distribution notices, and invoices. This tool reads each PDF, sorts it by type, pulls out the key fields, checks that the numbers add up, and sends doubtful ones to a person. It runs on a laptop with a local model, so no document leaves the machine.

All documents are synthetic. Every page says "SYNTHETIC SAMPLE, NOT A REAL NOTICE", and every fund, investor, and vendor name is invented.

## How it works

1. **Read** the text of the PDF with pypdf.
2. **Sort** it with TF-IDF and logistic regression. MiniLM embeddings give a second opinion.
3. **Extract** the fields with `qwen3:4b` through Ollama. The reply must fit a Pydantic schema, and a bad reply gets one retry. The prompt shows a worked example: the most similar train document and its answer.
4. **Check** the arithmetic, for example that the parts of a capital call add up to its total. The extractor copies what the page says, even when it is wrong, so the checks can catch a wrong notice.
5. **Flag** the document for a person when the two type opinions disagree, extraction fails, or a check fails.

## Results

From [docs/results.md](docs/results.md), written by the evaluate command. The test set has 45 documents, and none of them was used for training or retrieval. The last column runs the same pipeline without the worked example.

| Measure | With worked example | Without |
|---|---|---|
| Type right | 45/45 | 45/45 |
| Fields right | 570/570 | 561/570 |
| Documents with every field right | 45/45 | 37/45 |
| Amounts wrong | 0 | 0 |
| Planted arithmetic errors caught | 6/6 | 6/6 |
| Clean documents flagged by mistake | 0/39 | 0/39 |
| Model time per document | 22.1 seconds | 23.6 seconds |

Read these numbers with care.

1. The data is synthetic, from one generator with 3 page layouts per type. The worked example comes from the same generator, so it nearly always matches the layout. The field hints in the prompt were also written knowing the generator's own label words. Real notices vary far more. These scores show the method works on this data, not on a real inbox.
2. Without the worked example, the model copied a heading as an invoice line, and sometimes put a stray colon inside a name or an invoice number. Every miss was in text. No amount was wrong in either run.
3. The test set is small, so one document moves a score a lot.

## Run it

You need macOS or Linux, [uv](https://docs.astral.sh/uv/), and [Ollama](https://ollama.com). It was built on an 8 GB M1 MacBook Air.

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
ollama pull qwen3:4b
export FUND_NOTICES_MODEL=qwen3:4b
.venv/bin/python -m fund_notices.generate
.venv/bin/python -m fund_notices.process samples/test_013.pdf
.venv/bin/python -m fund_notices.evaluate
```

`generate` builds the documents. `process` reads one PDF and prints what it found. `evaluate` scores the test set and rewrites `docs/results.md`. Replies are cached in `cache/`, so a rerun is fast and gives the same numbers.

## The demo page

```bash
.venv/bin/streamlit run src/fund_notices/app.py
```

Open `http://localhost:8501`, pick a test document or upload a PDF, and press Read it. Try `test_013`. It has a planted error, and the page sends it to a person. The page only listens on this laptop.

## Learn more

- [Code guide](docs/guide/code-guide.md): every module, in reading order.
- [Decisions](docs/DECISIONS.md): what was chosen, and why.
- [Data format](docs/reference/data-format.md): the fields and the answer files.
- [Results](docs/results.md): the full scores, every flagged document, and every wrong field.
