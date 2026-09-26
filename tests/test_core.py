"""Basic tests for fetchly core. Network tests hit example.com (reliable)."""
import pytest

from fetchly import core


def test_fetch_returns_markdown_and_title():
    page = core.fetch_url("https://example.com")
    assert page["title"] == "Example Domain"
    assert "example" in page["markdown"].lower()
    assert page["link_count"] >= 1


def test_search_returns_cited_results():
    out = core.search("model context protocol", limit=3)
    assert out["count"] >= 1
    for r in out["results"]:
        assert r["url"].startswith("http")
        assert "source" in r


def test_summarize_orders_sentences():
    text = (
        "SharedNet is a network of Rooms where coding agents talk. "
        "Each agent has an address. "
        "The goal is to let one billion agents collaborate on hard problems."
    )
    out = core.summarize(text, n=2)
    assert len(out["sentences"]) == 2
    # sentences appear in their original order
    assert out["sentences"][0].startswith("SharedNet")
    assert out["summary"].count(".") >= 1


def test_extract_links_dedupes_and_absolutizes():
    links = core.extract_links(
        b'<html><a href="/a">A</a><a href="/a">A again</a><a href="http://x/b">B</a></html>',
        "https://example.com/",
    )
    urls = [l["url"] for l in links]
    assert urls == ["https://example.com/a", "http://x/b"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
