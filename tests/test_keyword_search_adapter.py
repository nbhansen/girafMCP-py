"""Tests for KeywordSearchAdapter."""

from pathlib import Path

import pytest

from girafmcp.adapters.keyword_search_adapter import KeywordSearchAdapter


def _write_md(path: Path, title: str, tags: list[str], body: str) -> None:
    """Helper to write a markdown file with frontmatter."""
    tag_lines = "\n".join(f"- {t}" for t in tags)
    content = f"""---
title: {title}
tags:
{tag_lines}
---
{body}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def adapter_with_docs(tmp_path: Path) -> KeywordSearchAdapter:
    """Create adapter with sample documents."""
    _write_md(
        tmp_path / "doc1.md",
        "FoodPlanner Report",
        ["handover", "semester"],
        "The foodplanner application uses Flutter for the frontend. "
        "Authentication is handled via JWT tokens. "
        "The foodplanner was redesigned in sprint 3.",
    )
    _write_md(
        tmp_path / "doc2.md",
        "VTA Report",
        ["handover", "research"],
        "Visual tangible artefacts help children with autism. "
        "The VTA app uses NFC tags for interaction.",
    )
    _write_md(
        tmp_path / "subdir/doc3.md",
        "Week Planner",
        ["documentation"],
        "The week planner uses TypeScript and React.",
    )
    return KeywordSearchAdapter(extracted_dir=tmp_path)


async def test_search_returns_results(adapter_with_docs: KeywordSearchAdapter) -> None:
    results = await adapter_with_docs.search("foodplanner")
    assert len(results) == 1
    assert results[0].title == "FoodPlanner Report"
    assert results[0].score > 0


async def test_search_scores_by_frequency(adapter_with_docs: KeywordSearchAdapter) -> None:
    results = await adapter_with_docs.search("foodplanner", limit=5)
    # "foodplanner" appears twice in doc1, zero in others
    assert len(results) == 1
    assert results[0].score == 2


async def test_search_multiple_keywords(adapter_with_docs: KeywordSearchAdapter) -> None:
    results = await adapter_with_docs.search("flutter foodplanner")
    assert len(results) == 1
    assert results[0].title == "FoodPlanner Report"


async def test_search_case_insensitive(adapter_with_docs: KeywordSearchAdapter) -> None:
    results = await adapter_with_docs.search("FOODPLANNER")
    assert len(results) == 1


async def test_search_with_tag_filter(adapter_with_docs: KeywordSearchAdapter) -> None:
    results = await adapter_with_docs.search("handover", tags=["research"])
    # Only doc2 has "research" tag and contains "handover" in... wait, we search body not tags
    # doc2 doesn't contain "handover" in body. Let's search for something in doc2.
    results = await adapter_with_docs.search("autism", tags=["research"])
    assert len(results) == 1
    assert results[0].title == "VTA Report"


async def test_search_tag_filter_excludes(adapter_with_docs: KeywordSearchAdapter) -> None:
    results = await adapter_with_docs.search("foodplanner", tags=["research"])
    assert len(results) == 0


async def test_search_respects_limit(adapter_with_docs: KeywordSearchAdapter) -> None:
    # Search for a common word
    results = await adapter_with_docs.search("the", limit=2)
    assert len(results) <= 2


async def test_search_empty_dir() -> None:
    adapter = KeywordSearchAdapter(extracted_dir=None)
    results = await adapter.search("test")
    assert results == []


async def test_search_no_match(adapter_with_docs: KeywordSearchAdapter) -> None:
    results = await adapter_with_docs.search("zzzznonexistent")
    assert results == []


async def test_list_documents(adapter_with_docs: KeywordSearchAdapter) -> None:
    docs = await adapter_with_docs.list_documents()
    assert len(docs) == 3
    titles = {d.title for d in docs}
    assert "FoodPlanner Report" in titles
    assert "VTA Report" in titles
    assert "Week Planner" in titles


async def test_list_documents_empty_dir() -> None:
    adapter = KeywordSearchAdapter(extracted_dir=None)
    docs = await adapter.list_documents()
    assert docs == []


async def test_list_documents_has_tags(adapter_with_docs: KeywordSearchAdapter) -> None:
    docs = await adapter_with_docs.list_documents()
    fp_doc = next(d for d in docs if d.title == "FoodPlanner Report")
    assert "handover" in fp_doc.tags
    assert "semester" in fp_doc.tags


async def test_search_snippet_contains_context(adapter_with_docs: KeywordSearchAdapter) -> None:
    results = await adapter_with_docs.search("JWT")
    assert len(results) == 1
    assert "JWT" in results[0].snippet


async def test_search_finds_in_subdirectories(adapter_with_docs: KeywordSearchAdapter) -> None:
    results = await adapter_with_docs.search("TypeScript")
    assert len(results) == 1
    assert results[0].title == "Week Planner"
