from pathlib import Path

from docs_check import check_docs, read_frontmatter

GOOD_FRONTMATTER = "---\ntype: t\npurpose: p\nowner: o\nreviewed: 2026-10-08\n---\n"


def make_repo(tmp_path: Path, index_body: str) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text(GOOD_FRONTMATTER + "# Readme\n")
    (tmp_path / "docs" / "STATUS.md").write_text(GOOD_FRONTMATTER + "# Status\n")
    (tmp_path / "docs" / "INDEX.md").write_text(GOOD_FRONTMATTER + index_body)
    return tmp_path


def test_clean_repo_passes(tmp_path: Path) -> None:
    root = make_repo(tmp_path, "- [README](../README.md)\n- [STATUS](STATUS.md)\n")
    assert check_docs(root) == []


def test_missing_frontmatter_key_is_reported(tmp_path: Path) -> None:
    root = make_repo(tmp_path, "- [README](../README.md)\n- [STATUS](STATUS.md)\n")
    (root / "docs" / "STATUS.md").write_text("---\ntype: t\npurpose: p\nowner: o\n---\n")
    assert check_docs(root) == ["docs/STATUS.md: frontmatter is missing 'reviewed'"]


def test_doc_not_in_index_is_reported(tmp_path: Path) -> None:
    root = make_repo(tmp_path, "- [README](../README.md)\n")
    assert check_docs(root) == ["docs/STATUS.md: not listed in docs/INDEX.md"]


def test_dead_link_in_index_is_reported(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path, "- [README](../README.md)\n- [STATUS](STATUS.md)\n- [Gone](GONE.md)\n"
    )
    assert check_docs(root) == ["docs/INDEX.md: dead link 'GONE.md'"]


def test_unclosed_frontmatter_counts_as_none() -> None:
    assert read_frontmatter("---\ntype: t\n# no closing line\n") is None
