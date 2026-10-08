"""Check that the docs follow the repo's rules.

Rules:
1. Every doc starts with frontmatter holding type, purpose, owner, and reviewed.
2. Every doc is linked from docs/INDEX.md.
3. Every link in docs/INDEX.md points to a file that exists.

Exit code 0 means all rules pass. Exit code 1 means at least one failed.
"""

import re
import sys
from pathlib import Path

REQUIRED_KEYS = ("type", "purpose", "owner", "reviewed")
ROOT_DOCS = ("README.md", "AGENTS.md", "CLAUDE.md")
INDEX = Path("docs/INDEX.md")
LINK = re.compile(r"\]\(([^)#\s]+)\)")


def find_docs(root: Path) -> list[Path]:
    """Return every doc path, relative to root."""
    docs = [Path(name) for name in ROOT_DOCS if (root / name).is_file()]
    docs += sorted(p.relative_to(root) for p in (root / "docs").rglob("*.md"))
    return docs


def read_frontmatter(text: str) -> dict[str, str] | None:
    """Return the frontmatter keys and values, or None if there is no frontmatter block."""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None
    values: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return values
        key, sep, value = line.partition(":")
        if sep:
            values[key.strip()] = value.strip()
    return None


def check_docs(root: Path) -> list[str]:
    """Return a list of problems. An empty list means every rule passes."""
    problems: list[str] = []
    docs = find_docs(root)

    for doc in docs:
        frontmatter = read_frontmatter((root / doc).read_text(encoding="utf-8"))
        if frontmatter is None:
            problems.append(f"{doc}: no frontmatter block")
            continue
        for key in REQUIRED_KEYS:
            if not frontmatter.get(key):
                problems.append(f"{doc}: frontmatter is missing '{key}'")

    index_path = root / INDEX
    if not index_path.is_file():
        problems.append(f"{INDEX}: file not found")
        return problems

    linked: set[Path] = set()
    for target in LINK.findall(index_path.read_text(encoding="utf-8")):
        resolved = (index_path.parent / target).resolve()
        if not resolved.is_file():
            problems.append(f"{INDEX}: dead link '{target}'")
        else:
            linked.add(resolved)

    for doc in docs:
        if doc != INDEX and (root / doc).resolve() not in linked:
            problems.append(f"{doc}: not listed in {INDEX}")

    return problems


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    problems = check_docs(root)
    for problem in problems:
        print(problem)
    print("docs check passed" if not problems else f"docs check failed: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
