---
type: status
purpose: The only status document. What is done, what is next, and where we are.
owner: Kshitij
reviewed: 2026-10-12
---

# Status

Current: Day 1, Block 2 is done. Next is Day 2.

## Done

1. Day 1, Block 1: project setup with uv and Python 3.12, the docs system, `scripts/docs_check.py`, and the Pydantic schema for capital calls, distributions, and invoices. Kshitij wrote `DistributionNotice`.
2. Day 1, Block 2: the PDF generator. `python -m fund_notices.generate` writes 42 train and 45 test documents with answer files, 3 layouts per type, and 6 planted arithmetic mistakes in the test set. Two samples are in `samples/`. Kshitij wrote `shift_field`.

## Next

1. Before Day 2: confirm the Ollama model for an 8 GB Mac.
2. Day 2: plan to be agreed at the start of the block.
