---
type: status
purpose: The only status document. What is done, what is next, and where we are.
owner: Kshitij
reviewed: 2026-10-13
---

# Status

Current: The project is complete. The pipeline runs end to end, and `docs/results.md` holds the scores from the evaluate command.

## Done

1. Day 1, Block 1: project setup with uv and Python 3.12, the docs system, `scripts/docs_check.py`, and the Pydantic schema for capital calls, distributions, and invoices. Kshitij wrote `DistributionNotice`.
2. Day 1, Block 2: the PDF generator. `python -m fund_notices.generate` writes 42 train and 45 test documents with answer files, 3 layouts per type, and 6 planted arithmetic mistakes in the test set. Two samples are in `samples/`. Kshitij wrote `shift_field`.
3. Day 2, Block 2: PDF text reading, the LLM interface, the Ollama client, the disk cache, and extraction with one retry. Tests use fake clients.
4. Day 2, Block 3: math checks for all three types, field scoring, and `python -m fund_notices.compare` to try models on train documents.
5. The code guide in `docs/guide/code-guide.md`.
6. Model chosen: `qwen3:4b`, with thinking off and every key required. See decisions 15 and 16.
7. Day 2, Block 1, done last: the baseline classifier with TF-IDF and logistic regression. Kshitij wrote `predict`.
8. Day 3: retrieval with MiniLM and TF-IDF, the worked example in the prompt, the pipeline with the review decision, `python -m fund_notices.process` for one PDF, `python -m fund_notices.evaluate` for the test set, the README, and a Streamlit demo page. See decisions 18 to 22.

## Next

1. Kshitij reads the code guide end to end and answers the questions in `misc/interview-questions.md`.
2. Optional ideas, none started: a larger model where memory allows, more layouts in the generator, and a review queue that says which number looks wrong.
