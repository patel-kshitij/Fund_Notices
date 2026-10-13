---
type: guide
purpose: Hard rules and working style for any AI agent pairing on this repo. Read first, every session.
owner: Kshitij
reviewed: 2026-10-08
---

# AGENTS.md

Read this file first, every session. Then read docs/STATUS.md to see where we are.

## Hard rules

1. Never run git in any form, and never touch GitHub. Kshitij reviews and commits every change.
2. All data is synthetic. Every generated PDF carries the line "SYNTHETIC SAMPLE, NOT A REAL NOTICE". Fund, investor, vendor, and bank names are invented. Bank details are obviously fake.
3. Never name the employer Kshitij is applying to anywhere in the repo.
4. Never put a number in the README or docs that did not come from running the evaluate command. Report failures and bad scores as they are.
5. Install nothing globally. Use the `.venv` inside the project. Ask before adding any dependency outside the stack below.
6. No LangChain, LlamaIndex, or other agent frameworks. Plain library calls only.
7. Typed Python everywhere. pytest, ruff, mypy, and `scripts/docs_check.py` must all pass at the end of every block.
8. Money is `Decimal`, never `float`.
9. Docs, comments, and the README use plain English and short sentences. Never put a dash inside a sentence.

## The LLM runs locally

1. The LLM runs on this laptop with Ollama, called through the `ollama` Python package. It is free and no document leaves the machine.
2. There is no Anthropic API, no API key, and no `.env` file.
3. The model name comes from an environment variable. The LLM sits behind one small interface, so a cloud model can be added later without touching the rest of the code.
4. Extraction passes the Pydantic model's JSON schema to Ollama's `format` parameter, validates the reply with Pydantic, and retries once with the validation error.
5. Tests never call Ollama. They use a fake client.
6. The evaluate command reports model calls and run time, not cost.

## Stack

Python 3.12 (managed by uv), src layout, pyproject.toml. fpdf2 and pypdf for PDFs. pandas and NumPy for scoring. scikit-learn for the baseline. sentence-transformers with all-MiniLM-L6-v2 for embeddings. ollama for the LLM. Streamlit for the demo page. Pydantic v2, pytest, ruff, mypy.

## How we work

1. Work in blocks of about 45 minutes. At the start, say in 2 or 3 lines what the block will finish.
2. Before writing a new piece, explain the plan in plain English and wait for an OK.
3. Now and then, ask Kshitij to write a small piece, then review it honestly.
4. After writing tests, give one line per test on the behavior it protects.
5. For a decision, give 2 to 4 concrete options with a recommendation.
6. If unsure, say so and show the evidence. Do not guess.
7. End each block with one interview question, then feedback on the answer.

## Block handover

1. Update docs/STATUS.md.
2. Give a commit message with no attribution trailer of any kind.
3. Give the exact commands to run in one bash code block with no comments and no prose.

## Commands

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/pytest
.venv/bin/python scripts/docs_check.py
```
