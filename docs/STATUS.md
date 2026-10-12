---
type: status
purpose: The only status document. What is done, what is next, and where we are.
owner: Kshitij
reviewed: 2026-10-12
---

# Status

Current: Day 2, Blocks 2 and 3 are done in code. The model choice waits for Ollama to be installed.

## Done

1. Day 1, Block 1: project setup with uv and Python 3.12, the docs system, `scripts/docs_check.py`, and the Pydantic schema for capital calls, distributions, and invoices. Kshitij wrote `DistributionNotice`.
2. Day 1, Block 2: the PDF generator. `python -m fund_notices.generate` writes 42 train and 45 test documents with answer files, 3 layouts per type, and 6 planted arithmetic mistakes in the test set. Two samples are in `samples/`. Kshitij wrote `shift_field`.
3. Day 2, Block 2: PDF text reading, the LLM interface, the Ollama client, the disk cache, and extraction with one retry. Tests use fake clients.
4. Day 2, Block 3: math checks for all three types, field scoring, and `python -m fund_notices.compare` to try models on train documents.
5. The code guide in `docs/guide/code-guide.md`.

## Next

1. Kshitij installs the Ollama app and pulls `qwen3:4b` and `llama3.2:3b`.
2. Run `python -m fund_notices.compare qwen3:4b llama3.2:3b` and record the chosen model as a decision. No model has been run yet.
3. Day 2, Block 1, moved later: the baseline classifier with TF-IDF and logistic regression. Needs `scikit-learn`.
4. Then: embeddings and retrieval, and the evaluate command.
