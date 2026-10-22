#!/usr/bin/env python3
"""
ServiceNow Documentation Harvester v3

Downloads official docs via the FluidTopics khub API at
https://www.servicenow.com/docs/api/khub/

No authentication required. No external dependencies beyond Python 3 stdlib.
Optional: pip install html2text for better markdown conversion.

Usage:
    python3 harvest.py --search "CMDB health" --list
    python3 harvest.py --search "CICD API" -o cicd-api.md -v   # top hit's topic and its children
    python3 harvest.py --map-id q4dSP2Icgr1SFv5wanVXvQ -o platform.md -v
    python3 harvest.py --map-id MAP --subtree CONTENT_ID -o cmdb.md -v
    python3 harvest.py --search "Fluent API" --list --lang ja-JP   # default en-US; "all" disables
    python3 harvest.py --map-id MAP --subtree BIG_PAGE -o big.md --timeout 120
"""
import argparse, http.client, json, math, re, sys, time, urllib.error, urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TypeVar

API_BASE = "https://www.servicenow.com/docs/api/khub"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}
DELAY = 0.25
TIMEOUT = 30  # seconds per request; --timeout overrides for large single-page topics
RETRY_DELAYS = (1, 2, 4)  # backoff in seconds before each retry of a 429, 5xx or network failure
MAX_RETRY_AFTER = 60  # cap on a server-sent Retry-After, in seconds
MAX_CONSECUTIVE_FAILURES = 5  # give up on a harvest after this many failed topics in a row

try:
    import html2text as _h2t
    _c = _h2t.HTML2Text()
    _c.body_width = 0; _c.ignore_links = False; _c.ignore_images = True
    _c.ignore_tables = False; _c.unicode_snob = True; _c.skip_internal_links = True
    def html_to_md(html): return _c.handle(html)
except ImportError:
    def html_to_md(html):
        t = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html)
        t = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", t)
        t = re.sub(r"<br\s*/?>", "\n", t); t = re.sub(r"</p>", "\n\n", t)
        t = re.sub(r"<h([1-6])[^>]*>(.*?)</h\1>", lambda m: "#"*int(m.group(1))+" "+m.group(2)+"\n", t)
        t = re.sub(r"<[^>]+>", "", t)
        for e, c in [("&amp;","&"),("&lt;","<"),("&gt;",">"),("&nbsp;"," ")]: t = t.replace(e, c)
        return re.sub(r"\n{3,}", "\n\n", t).strip()

def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))

def _post(url, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))

def _html(url):
    req = urllib.request.Request(url, headers={"Accept":"*/*","User-Agent":HEADERS["User-Agent"]})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")

T = TypeVar("T")

def _retry_after(e: urllib.error.HTTPError) -> float | None:
    """Seconds from a Retry-After header (delta-seconds form only), capped at MAX_RETRY_AFTER."""
    value = e.headers.get("Retry-After") if e.headers else None
    try: seconds = float(value) if value else None
    except ValueError: return None
    if seconds is None or not math.isfinite(seconds): return None
    return min(max(0.0, seconds), MAX_RETRY_AFTER)

def _retry(fetch: Callable[[], T]) -> T:
    """Call fetch(), retrying 429, 5xx, network errors and timeouts after each of RETRY_DELAYS
    (or the server's Retry-After); the last failure, or any other HTTP error, is raised.
    Only for idempotent GETs: a request may be sent again after the server got it."""
    for delay in RETRY_DELAYS:
        try: return fetch()
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500: raise
            retry_after = _retry_after(e)
            wait = delay if retry_after is None else retry_after
        # OSError covers URLError, timeouts and connection resets; HTTPException covers
        # RemoteDisconnected and IncompleteRead
        except (OSError, http.client.HTTPException):
            wait = delay
        time.sleep(wait)
    return fetch()

_map_lang = {}  # mapId -> locale, e.g. "en-US"

def map_lang(map_id):
    """Locale of a map, from its metadata (fetched once per mapId)."""
    if map_id not in _map_lang:
        try: _map_lang[map_id] = _get(f"{API_BASE}/maps/{map_id}").get("lang", "")
        except Exception: _map_lang[map_id] = ""
    return _map_lang[map_id]

def search(query, limit=30, lang="en-US"):
    """Search topics. Every map exists in several locales, often with English titles,
    so results are filtered to maps in `lang` ("all" or "" disables the filter)."""
    data = _post(f"{API_BASE}/clustered-search", {"query": query})
    want = "" if lang in ("", "all") else lang.lower()
    entries = []
    for cluster in data.get("results", []):
        for entry in cluster.get("entries", []):
            topic = entry.get("topic", {})
            if topic and topic.get("mapId"):
                mid = topic["mapId"]
                if mid not in _map_lang:  # topic metadata usually carries ft:locale; saves a request
                    md = {m.get("key"): m.get("values", []) for m in topic.get("metadata", [])}
                    if md.get("ft:locale"): _map_lang[mid] = md["ft:locale"][0]
                if want and map_lang(mid).lower() != want: continue
                entries.append({
                    "mapId": mid, "contentId": topic.get("contentId",""),
                    "title": topic.get("title",""), "mapTitle": topic.get("mapTitle",""),
                    "lang": map_lang(mid),
                    "excerpt": re.sub(r"<[^>]+>","",topic.get("htmlExcerpt","")),
                })
            if len(entries) >= limit: break
        if len(entries) >= limit: break
    return entries

def fetch_toc(map_id):
    return _retry(lambda: _get(f"{API_BASE}/maps/{map_id}/pages")).get("paginatedToc", [])

def walk_toc(pages, depth=0):
    for page in pages:
        cid = page.get("contentId")
        if cid: yield (cid, page.get("title",""), depth)
        for child in page.get("children", []): yield from walk_toc([child], depth+1)

def find_subtree(pages, target_id):
    for page in pages:
        if page.get("contentId") == target_id: return page
        found = find_subtree(page.get("children",[]), target_id)
        if found: return found
    return None

def subtree_or_exit(toc, map_id, subtree_id):
    """The TOC node for subtree_id; exits 1 with a hint if the map has no such contentId."""
    node = find_subtree(toc, subtree_id)
    if not node:
        print(f"ERROR: subtree {subtree_id} not found in map {map_id}; list its contentIds with "
              f"--map-id {map_id} --show-toc and pass one as --subtree", file=sys.stderr)
        sys.exit(1)
    return node

def _missing_marker(cid: str, title: str) -> str:
    """An output line recording a topic that could not be fetched ("--" cannot appear in a comment)."""
    return f"\n<!-- missing: {cid} {re.sub(r'-{2,}', '-', title)} -->\n"

def harvest(map_id, output_path, subtree_id=None, verbose=False):
    """Write the map (or subtree) to output_path; returns the number of topics that failed.
    Each failure is logged to stderr and left as a <!-- missing: ... --> marker in the output.
    After MAX_CONSECUTIVE_FAILURES failed topics in a row the rest are not attempted, only marked."""
    try:
        meta = _get(f"{API_BASE}/maps/{map_id}")
        map_title = meta.get("title", "ServiceNow Documentation")
    except: map_title = "ServiceNow Documentation"
    if verbose: print(f"Map: {map_title}")
    if verbose: print("Fetching TOC...")
    toc = fetch_toc(map_id)
    if subtree_id:
        node = subtree_or_exit(toc, map_id, subtree_id)
        topics = list(walk_toc([node]))
        map_title = node.get("title", map_title)
        if verbose: print(f"Subtree: {map_title}")
    else:
        topics = list(walk_toc(toc))
    if verbose: print(f"Topics: {len(topics)} (est. {len(topics)*DELAY/60:.1f} min)")
    lines = [f"<!-- Source: servicenow.com/docs | Map: {map_id} | Harvested: {datetime.now().strftime('%Y-%m-%d')} -->", f"# {map_title}\n"]
    fetched = skipped = errors = streak = 0; not_tried = []; t0 = time.time()
    for i, (cid, title, depth) in enumerate(topics):
        time.sleep(DELAY)
        url = f"{API_BASE}/maps/{map_id}/topics/{cid}/content"
        try: html = _retry(lambda: _html(url))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                skipped += 1; streak = 0; print(f"  SKIPPED (404): {cid} {title}", file=sys.stderr); continue
            failure = f"HTTP {e.code}"
        except Exception as e: failure = str(e) or type(e).__name__
        else: failure = None
        if failure:
            errors += 1; streak += 1; print(f"  ERROR: {cid} {title}: {failure}", file=sys.stderr)
            lines.append(_missing_marker(cid, title))
            if streak >= MAX_CONSECUTIVE_FAILURES:
                not_tried = topics[i + 1:]
                print(f"ERROR: {streak} topics in a row failed; giving up on the remaining {len(not_tried)} "
                      "(marked missing in the output)", file=sys.stderr)
                lines.extend(_missing_marker(c, t) for c, t, _ in not_tried)
                break
            continue
        streak = 0
        if not html or len(html.strip()) < 50: skipped += 1; continue
        md = html_to_md(html)
        heading = "#" * min(depth + 2, 6)
        lines.append(f"\n{heading} {title}\n"); lines.append(md); lines.append("\n---\n")
        fetched += 1
        if verbose and fetched % 50 == 0:
            elapsed = time.time() - t0
            remaining = (len(topics) - fetched - skipped - errors) * DELAY
            print(f"  [{fetched}/{len(topics)}] ~{remaining:.0f}s left | {title[:50]}")
    out = Path(output_path); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    sz = out.stat().st_size / 1024; elapsed = time.time() - t0
    untried = f", {len(not_tried)} not attempted" if not_tried else ""
    print(f"\nDone: {fetched} fetched, {skipped} skipped, {errors} errors{untried} ({elapsed:.0f}s)")
    print(f"Output: {output_path} ({sz:.0f}K)")
    missing = errors + len(not_tried)
    if missing: print(f"ERROR: {missing} topics missing (see above); output has <!-- missing --> markers", file=sys.stderr)
    return missing

def main():
    p = argparse.ArgumentParser(description="Harvest ServiceNow docs from /docs/api/khub/")
    p.add_argument("--search", help="Search query"); p.add_argument("--map-id", help="Map ID")
    p.add_argument("--subtree", help="ContentId of subtree to harvest")
    p.add_argument("--output", "-o", help="Output file"); p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--list", action="store_true"); p.add_argument("--show-toc", action="store_true")
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--lang", default="en-US", help='Map locale to keep (default en-US; "all" for every locale)')
    p.add_argument("--timeout", type=float, default=30, help="Per-request timeout in seconds (default 30)")
    args = p.parse_args()
    global TIMEOUT; TIMEOUT = args.timeout
    if args.search:
        results = search(args.search, limit=args.limit, lang=args.lang)
        if not results: print(f"No results for: {args.search} (lang {args.lang})"); sys.exit(1)
        maps = {}
        for r in results:
            mid = r["mapId"]
            if mid not in maps: maps[mid] = {"mapTitle": r["mapTitle"], "lang": r["lang"], "topics": []}
            maps[mid]["topics"].append(r["title"])
        if args.list or not args.output:
            print(f"Search results for '{args.search}' (lang {args.lang}):\n")
            for i, (mid, info) in enumerate(maps.items()):
                print(f"  [{i}] {info['mapTitle']} [{info['lang'] or '?'}] (mapId: {mid})")
                for t in info["topics"][:3]: print(f"      - {t}")
                if len(info["topics"]) > 3: print(f"      ... +{len(info['topics'])-3} more")
            if not args.output: print(f"\nTo download, add: --output <filename.md>")
            return
        first_map_id = results[0]["mapId"]  # maps keeps result order, so this is the top hit's map
        # Harvest the top hit's topic and its children, not the whole map that contains it
        subtree_id = args.subtree or results[0]["contentId"]
        if not subtree_id: p.error("top search result has no contentId; pass --map-id with --subtree")
        if args.verbose: print(f"Using map: {maps[first_map_id]['mapTitle']} ({first_map_id})")
        if harvest(first_map_id, args.output, subtree_id=subtree_id, verbose=args.verbose): sys.exit(1)
    elif args.map_id:
        lang = map_lang(args.map_id)
        if args.lang not in ("", "all") and lang and lang.lower() != args.lang.lower():
            print(f"WARNING: map {args.map_id} is {lang}, not {args.lang}; proceeding", file=sys.stderr)
        if args.show_toc:
            toc = fetch_toc(args.map_id)
            tree = [subtree_or_exit(toc, args.map_id, args.subtree)] if args.subtree else toc
            for cid, title, depth in walk_toc(tree):
                print(f"{'  '*depth}{title} ({cid})")
            return
        if not args.output: p.error("--output required with --map-id")
        if harvest(args.map_id, args.output, subtree_id=args.subtree, verbose=args.verbose): sys.exit(1)
    else: p.error("Either --search or --map-id is required")

if __name__ == "__main__": main()
