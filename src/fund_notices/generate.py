"""Write the synthetic data set to disk.

Run with: python -m fund_notices.generate

It writes data/train and data/test, one PDF and one JSON answer file per
document, then copies two of them to samples/ so they can be committed.
"""

import shutil
from pathlib import Path

from fund_notices.render import render_pdf
from fund_notices.schema import AnswerFile, DocType
from fund_notices.synth import build_dataset

ROOT = Path(__file__).resolve().parents[2]


def write_split(answers: list[AnswerFile], folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    # Remove files from an earlier run, so no stale document is left behind.
    for old in [*folder.glob("*.pdf"), *folder.glob("*.json")]:
        old.unlink()
    for answer in answers:
        (folder / f"{answer.doc_id}.pdf").write_bytes(render_pdf(answer))
        (folder / f"{answer.doc_id}.json").write_text(
            answer.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )


def pick_samples(train: list[AnswerFile], test: list[AnswerFile]) -> list[AnswerFile]:
    """One clean capital call from train, and one test notice with a planted error."""
    clean = next(a for a in train if a.doc_type == DocType.CAPITAL_CALL and a.title)
    flawed = next(a for a in test if a.planted_error is not None)
    return [clean, flawed]


def main() -> None:
    train, test = build_dataset()
    data = ROOT / "data"
    write_split(train, data / "train")
    write_split(test, data / "test")

    samples = ROOT / "samples"
    samples.mkdir(exist_ok=True)
    for answer in pick_samples(train, test):
        for suffix in (".pdf", ".json"):
            name = f"{answer.doc_id}{suffix}"
            shutil.copy(data / answer.split / name, samples / name)

    planted = sum(a.planted_error is not None for a in test)
    print(f"train: {len(train)} documents, test: {len(test)} documents, planted errors: {planted}")


if __name__ == "__main__":
    main()
