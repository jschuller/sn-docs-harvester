"""Tests for scripts/harvest.py. No network: _get, _post and _html are replaced per test."""

from __future__ import annotations

import email.message
import http.client
import importlib.util
import math
import sys
import urllib.error
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import harvest

MAP_ID = "MAP1"
OTHER_MAP_ID = "MAP2"

# Root > (Intro, API > (Endpoints > Details), Other)
TOC: list[dict[str, Any]] = [
    {
        "contentId": "root",
        "title": "Root",
        "children": [
            {"contentId": "intro", "title": "Intro"},
            {
                "contentId": "api",
                "title": "API",
                "children": [
                    {
                        "contentId": "endpoints",
                        "title": "Endpoints",
                        "children": [{"contentId": "details", "title": "Details"}],
                    }
                ],
            },
            {"contentId": "other", "title": "Other"},
        ],
    }
]


def http_error(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://example.invalid", code, "error", headers, None)


def page(cid: str) -> str:
    return f"<p>Body of topic {cid}, long enough to pass the 50-character minimum.</p>"


def fake_get(url: str) -> dict[str, Any]:
    if url.endswith("/pages"):
        return {"paginatedToc": TOC}
    return {"title": "Test Map", "lang": "en-US"}


def search_hit(map_id: str, content_id: str, title: str) -> dict[str, Any]:
    return {
        "entries": [
            {
                "topic": {
                    "mapId": map_id,
                    "contentId": content_id,
                    "title": title,
                    "mapTitle": f"Map {map_id}",
                    "metadata": [{"key": "ft:locale", "values": ["en-US"]}],
                }
            }
        ]
    }


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Isolate module state and record time.sleep calls instead of sleeping."""
    calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        if seconds < 0 or math.isnan(seconds):  # as time.sleep does
            raise ValueError("sleep length must be non-negative")
        calls.append(seconds)

    monkeypatch.setattr(harvest, "DELAY", 0)
    monkeypatch.setattr(harvest, "_map_lang", {})
    monkeypatch.setattr(harvest.time, "sleep", fake_sleep)
    monkeypatch.setattr(harvest, "_get", fake_get)
    monkeypatch.setattr(
        harvest,
        "_post",
        lambda url, data: {
            "results": [search_hit(MAP_ID, "api", "API"), search_hit(OTHER_MAP_ID, "x", "X")]
        },
    )
    return calls


def html_from(responses: dict[str, list[str | Exception]]) -> Callable[[str], str]:
    """An _html replacement: each contentId pops its next response; others return a page."""

    def fetch(url: str) -> str:
        cid = url.rsplit("/topics/", 1)[1].split("/", 1)[0]
        queue = responses.get(cid)
        if not queue:
            return page(cid)
        result = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(result, Exception):
            raise result
        return result

    return fetch


def run_main(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["harvest.py", *args])
    try:
        harvest.main()
    except SystemExit as e:
        return int(e.code or 0)
    return 0


def test_walk_toc_yields_depth_first_with_depth() -> None:
    assert list(harvest.walk_toc(TOC)) == [
        ("root", "Root", 0),
        ("intro", "Intro", 1),
        ("api", "API", 1),
        ("endpoints", "Endpoints", 2),
        ("details", "Details", 3),
        ("other", "Other", 1),
    ]


def test_find_subtree_finds_nested_node_or_none() -> None:
    node = harvest.find_subtree(TOC, "endpoints")
    assert node is not None
    assert node["title"] == "Endpoints"
    assert harvest.find_subtree(TOC, "missing") is None


def test_search_output_harvests_top_hit_subtree(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float], tmp_path: Path
) -> None:
    fetched: list[str] = []

    def fake_html(url: str) -> str:
        fetched.append(url)
        return page(url)

    monkeypatch.setattr(harvest, "_html", fake_html)
    out = tmp_path / "out.md"
    assert run_main(monkeypatch, "--search", "api", "-o", str(out)) == 0
    assert [u.split("/topics/")[1].split("/")[0] for u in fetched] == ["api", "endpoints", "details"]
    assert all(f"/maps/{MAP_ID}/" in u for u in fetched)
    text = out.read_text()
    assert "# API\n" in text
    assert "Intro" not in text
    assert "Other" not in text


def test_search_with_subtree_not_in_map_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
    sleeps: list[float],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "out.md"
    code = run_main(monkeypatch, "--search", "api", "--subtree", "nope", "-o", str(out))
    assert code == 1
    err = capsys.readouterr().err
    assert "nope" in err
    assert "--show-toc" in err
    assert not out.exists()


def test_retry_succeeds_after_503_and_honours_retry_after(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    attempts: list[str] = []
    responses: list[str | Exception] = [http_error(503), http_error(429, retry_after="7"), "ok"]

    def fetch() -> str:
        attempts.append("x")
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    assert harvest._retry(fetch) == "ok"
    assert len(attempts) == 3
    assert sleeps == [1, 7]


def test_retry_does_not_retry_404(sleeps: list[float]) -> None:
    calls: list[int] = []

    def fetch() -> str:
        calls.append(1)
        raise http_error(404)

    with pytest.raises(urllib.error.HTTPError):
        harvest._retry(fetch)
    assert len(calls) == 1
    assert sleeps == []


def test_retry_covers_timeouts_and_url_errors(sleeps: list[float]) -> None:
    responses: list[str | Exception] = [TimeoutError("slow"), urllib.error.URLError("down"), "ok"]

    def fetch() -> str:
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    assert harvest._retry(fetch) == "ok"
    assert sleeps == [1, 2]


def failing_then(errors: list[Exception], result: str = "ok") -> Callable[[], str]:
    """A fetch that raises each of errors in turn, then returns result."""
    pending = list(errors)

    def fetch() -> str:
        if pending:
            raise pending.pop(0)
        return result

    return fetch


def test_retry_after_negative_nan_or_date_never_crashes_sleep(sleeps: list[float]) -> None:
    errors: list[Exception] = [
        http_error(429, retry_after="-5"),
        http_error(503, retry_after="nan"),
        http_error(503, retry_after="Wed, 21 Oct 2026 07:28:00 GMT"),
    ]
    assert harvest._retry(failing_then(errors)) == "ok"
    assert sleeps == [0, 2, 4]  # negative clamped to 0; NaN and dates fall back to backoff


def test_retry_after_is_capped(sleeps: list[float]) -> None:
    assert harvest._retry(failing_then([http_error(429, retry_after="999")])) == "ok"
    assert sleeps == [harvest.MAX_RETRY_AFTER]


def test_fetch_toc_survives_bad_retry_after(monkeypatch: pytest.MonkeyPatch, sleeps: list[float]) -> None:
    fetch = failing_then([http_error(503, retry_after="-1")])
    monkeypatch.setattr(harvest, "_get", lambda url: {"paginatedToc": TOC} if fetch() else {})
    assert harvest.fetch_toc(MAP_ID) == TOC


@pytest.mark.parametrize(
    "error",
    [
        ConnectionResetError("reset"),
        http.client.RemoteDisconnected("closed"),
        http.client.IncompleteRead(b""),
    ],
)
def test_retry_covers_dropped_connections(error: Exception, sleeps: list[float]) -> None:
    assert harvest._retry(failing_then([error, error, error])) == "ok"
    assert sleeps == [1, 2, 4]


def flat_toc(count: int) -> list[dict[str, Any]]:
    return [{"contentId": f"t{i}", "title": f"Topic {i}"} for i in range(count)]


def test_harvest_gives_up_after_consecutive_failures(
    monkeypatch: pytest.MonkeyPatch,
    sleeps: list[float],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []

    def down(url: str) -> str:
        calls.append(url)
        raise http_error(503)

    monkeypatch.setattr(harvest, "fetch_toc", lambda map_id: flat_toc(8))
    monkeypatch.setattr(harvest, "_html", down)
    out = tmp_path / "out.md"
    assert harvest.harvest(MAP_ID, str(out)) == 8
    limit = harvest.MAX_CONSECUTIVE_FAILURES
    assert len(calls) == limit * (len(harvest.RETRY_DELAYS) + 1)  # topics after the limit are not fetched
    text = out.read_text()
    assert all(f"<!-- missing: t{i} Topic {i} -->" in text for i in range(8))
    err = capsys.readouterr().err
    assert f"giving up on the remaining {8 - limit}" in err
    assert "8 topics missing" in err


def test_success_resets_the_consecutive_failure_count(
    monkeypatch: pytest.MonkeyPatch,
    sleeps: list[float],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    limit = harvest.MAX_CONSECUTIVE_FAILURES
    ok = f"t{limit - 1}"  # one success just before the limit is reached
    count = 2 * limit - 1

    def flaky(url: str) -> str:
        cid = url.rsplit("/topics/", 1)[1].split("/", 1)[0]
        if cid == ok:
            return page(cid)
        raise http_error(500)

    monkeypatch.setattr(harvest, "fetch_toc", lambda map_id: flat_toc(count))
    monkeypatch.setattr(harvest, "_html", flaky)
    out = tmp_path / "out.md"
    assert harvest.harvest(MAP_ID, str(out)) == count - 1  # every topic tried; none given up on
    assert "giving up" not in capsys.readouterr().err


def test_harvest_recovers_from_transient_503(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float], tmp_path: Path
) -> None:
    monkeypatch.setattr(harvest, "_html", html_from({"endpoints": [http_error(503), page("endpoints")]}))
    out = tmp_path / "out.md"
    assert harvest.harvest(MAP_ID, str(out), subtree_id="api") == 0
    text = out.read_text()
    assert "Endpoints" in text
    assert "missing" not in text
    assert 1 in sleeps


def test_permanent_500_exits_nonzero_with_missing_marker(
    monkeypatch: pytest.MonkeyPatch,
    sleeps: list[float],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    fetch = html_from({"endpoints": [http_error(500)]})

    def counting_html(url: str) -> str:
        calls.append(url)
        return fetch(url)

    monkeypatch.setattr(harvest, "_html", counting_html)
    out = tmp_path / "out.md"
    code = run_main(monkeypatch, "--map-id", MAP_ID, "--subtree", "api", "-o", str(out))
    assert code == 1
    assert sum("/topics/endpoints/" in u for u in calls) == len(harvest.RETRY_DELAYS) + 1
    text = out.read_text()
    assert "<!-- missing: endpoints Endpoints -->" in text
    assert "Details" in text  # later topics are still harvested
    assert "endpoints Endpoints" in capsys.readouterr().err


def test_404_is_logged_and_skipped_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
    sleeps: list[float],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(harvest, "_html", html_from({"details": [http_error(404)]}))
    out = tmp_path / "out.md"
    assert run_main(monkeypatch, "--map-id", MAP_ID, "--subtree", "api", "-o", str(out)) == 0
    assert "details Details" in capsys.readouterr().err
    assert "missing" not in out.read_text()


@pytest.fixture
def fallback_harvest(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """A fresh copy of harvest.py loaded with html2text unavailable, so the stdlib converter is used."""
    monkeypatch.setitem(sys.modules, "html2text", None)
    spec = importlib.util.spec_from_file_location("harvest_fallback", SCRIPTS / "harvest.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fallback_html_to_md(fallback_harvest: ModuleType) -> None:
    html = (
        "<html><head><style>p { color: red }</style><script>alert(1)</script></head>"
        "<body><h2>Title</h2><p>One &amp; two</p><p>Line<br/>break &lt;tag&gt;</p></body></html>"
    )
    md = fallback_harvest.html_to_md(html)
    assert "## Title" in md
    assert "One & two" in md
    assert "Line\nbreak <tag>" in md
    assert "alert" not in md
    assert "color" not in md


def test_show_toc_subtree_prints_only_that_subtree(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float], capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(monkeypatch, "--map-id", MAP_ID, "--show-toc", "--subtree", "api") == 0
    assert capsys.readouterr().out.splitlines() == [
        "API (api)",
        "  Endpoints (endpoints)",
        "    Details (details)",
    ]


def test_show_toc_unknown_subtree_fails_clearly(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float], capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(monkeypatch, "--map-id", MAP_ID, "--show-toc", "--subtree", "nope") == 1
    captured = capsys.readouterr()
    assert "subtree nope not found in map MAP1" in captured.err
    assert "--show-toc" in captured.err
    assert captured.out == ""


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_fallback_html_to_md_keeps_structure_and_decodes_entities_once(
    fallback_harvest: ModuleType,
) -> None:
    """fixtures/fallback_topic.html covers a multi-line heading, nested ordered and bullet lists, an <li><p>
    item, and entities that must be decoded exactly once (&amp;lt; is the text "&lt;", not a tag)."""
    md = fallback_harvest.html_to_md((FIXTURES / "fallback_topic.html").read_text(encoding="utf-8"))
    assert md + "\n" == (FIXTURES / "fallback_topic.md").read_text(encoding="utf-8")


def test_fallback_html_to_md_renders_tables_as_markdown(fallback_harvest: ModuleType) -> None:
    """fixtures/fallback_table.html: header row, multi-paragraph cell, pipe in a cell, short row."""
    md = fallback_harvest.html_to_md((FIXTURES / "fallback_table.html").read_text(encoding="utf-8"))
    assert md + "\n" == (FIXTURES / "fallback_table.md").read_text(encoding="utf-8")


def test_fallback_html_to_md_keeps_code_blocks_verbatim(fallback_harvest: ModuleType) -> None:
    """fixtures/fallback_pre.html: blank lines, trailing spaces, entities decoded once, inner markup
    dropped, and a fence longer than any backtick run in the code."""
    md = fallback_harvest.html_to_md((FIXTURES / "fallback_pre.html").read_text(encoding="utf-8"))
    assert md + "\n" == (FIXTURES / "fallback_pre.md").read_text(encoding="utf-8")


def test_fallback_mismatched_heading_does_not_swallow_the_page(
    fallback_harvest: ModuleType,
) -> None:
    html = "<h3>Short</h4><p>Body text.</p><h3>Next</h3><p>More.</p>"
    assert fallback_harvest.html_to_md(html) == "### Short\n\nBody text.\n\n### Next\n\nMore."


def test_fallback_table_cell_pipe_entities_stay_escaped(fallback_harvest: ModuleType) -> None:
    html = "<table><tr><th>Op</th><th>x</th></tr><tr><td>a | b</td><td>a &#124; b &vert; c</td></tr></table>"
    assert fallback_harvest.html_to_md(html) == "| Op | x |\n| --- | --- |\n| a \\| b | a \\| b \\| c |"


def test_fallback_nested_table_is_flattened_into_its_cell(fallback_harvest: ModuleType) -> None:
    html = (
        "<table><tr><th>A</th><th>B</th></tr>"
        "<tr><td><table><tr><td>x</td><td>y &amp;lt;</td></tr><tr><td>z</td></tr></table></td>"
        "<td>outer2</td></tr><tr><td>r3</td><td>r3b</td></tr></table><p>after</p>"
    )
    assert fallback_harvest.html_to_md(html) == (
        "| A | B |\n| --- | --- |\n| x, y &lt;; z | outer2 |\n| r3 | r3b |\n\nafter"
    )


def test_fallback_pre_in_a_table_cell_is_inline_code(fallback_harvest: ModuleType) -> None:
    html = "<table><tr><th>Ex</th></tr><tr><td>Run <pre>a &lt;\nb `c`</pre></td></tr></table>"
    assert fallback_harvest.html_to_md(html) == "| Ex |\n| --- |\n| Run `` a < b `c` `` |"


def test_fallback_nul_in_page_text_does_not_crash(fallback_harvest: ModuleType) -> None:
    html = "<p>bad \x00PRE7\x00 input</p><pre>x</pre>"
    assert fallback_harvest.html_to_md(html) == "bad PRE7 input\n\n```\nx\n```"
