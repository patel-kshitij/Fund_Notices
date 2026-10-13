"""Read one PDF with the whole pipeline and print what it found.

Run with: FUND_NOTICES_MODEL=qwen3:4b python -m fund_notices.process samples/test_013.pdf

It needs the train set, which python -m fund_notices.generate builds.
"""

import argparse
from pathlib import Path

from fund_notices.llm import CachedClient, OllamaClient, model_from_env
from fund_notices.pdftext import pdf_text
from fund_notices.pipeline import NoticeReader, load_split
from fund_notices.retrieve import minilm_embedder

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="the PDF to read")
    args = parser.parse_args()
    texts, answers = load_split(ROOT / "data" / "train")
    if not answers:
        raise SystemExit("No train documents. Run: python -m fund_notices.generate")
    client = CachedClient(OllamaClient(model_from_env()), ROOT / "cache")
    embed = minilm_embedder(ROOT / "cache" / "models")
    reader = NoticeReader.from_train(texts, answers, client, embed)
    outcome = reader.read(pdf_text(args.pdf))

    prediction = outcome.prediction
    print(f"Type: {prediction.doc_type} (probability {prediction.confidence:.2f})")
    print(f"Nearest train document by meaning: {outcome.second_opinion}")
    print(f"Worked example: {outcome.example_id}")
    fields = outcome.extraction.fields
    print("Fields:" if fields else f"Extraction failed: {outcome.extraction.error}")
    if fields:
        print(fields.model_dump_json(indent=2))
    print(f"Send to a person: {'yes' if outcome.needs_review else 'no'}")
    for reason in outcome.review_reasons:
        print(f"  {reason}")


if __name__ == "__main__":
    main()
