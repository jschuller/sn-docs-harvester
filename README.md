# sn-docs-harvester

A Claude Code / claude.ai skill that downloads official ServiceNow documentation
from `servicenow.com/docs` as local markdown, using the public FluidTopics khub API.
No authentication, no dependencies beyond the Python 3 standard library.

Built to keep offline, version-pinned reference docs (CMDB, CSDM, Flow Designer,
Integration Hub, ATF, CI/CD API, …) next to ServiceNow projects so an agent can
read the docs for the exact release it is targeting instead of guessing.

## What it does

- Searches the docs catalog and lists matching documentation maps (per release: Australia, Zurich, Yokohama, …)
- Walks a map's table of contents and fetches each topic's HTML
- Converts to markdown (uses `html2text` if installed, falls back to a built-in converter)
- Can harvest a single subtree of a large map (recommended — the platform map is thousands of topics)

## Install

**Claude Code** — clone and symlink into your skills directory:

```bash
git clone https://github.com/jschuller/sn-docs-harvester.git ~/src/sn-docs-harvester
ln -s ~/src/sn-docs-harvester ~/.claude/skills/sn-docs-harvester
pip install html2text   # optional, better markdown
```

**claude.ai** — zip the repo and upload it as a skill; add `www.servicenow.com`
to the proxy allowed domains.

## Usage

```bash
# Find maps
python3 scripts/harvest.py --search "CMDB health" --list

# Harvest the top search hit's topic and its children (not its whole map);
# --subtree overrides, and must be in the top hit's map
python3 scripts/harvest.py --search "CICD API" -o cicd-api.md -v

# Show a map's TOC
python3 scripts/harvest.py --map-id MAP_ID --show-toc

# Harvest one section of a map
python3 scripts/harvest.py --map-id MAP_ID --subtree CONTENT_ID -o cmdb.md -v

# Harvest a whole map
python3 scripts/harvest.py --map-id MAP_ID -o platform.md -v

# Another locale (default en-US; "all" disables), longer timeout for huge pages
python3 scripts/harvest.py --search "Fluent API" --list --lang ja-JP
python3 scripts/harvest.py --map-id MAP_ID --subtree CONTENT_ID -o cicd.md --timeout 180
```

Verified map and subtree IDs are in [`references/known-maps.md`](references/known-maps.md);
a worked example is in [`examples/cmdb-harvest.md`](examples/cmdb-harvest.md).
The skill definition Claude reads is [`SKILL.md`](SKILL.md).

## Notes

- Requests are throttled (250 ms between topic fetches). Be considerate: harvest subtrees, not the whole catalog.
- 429, 5xx and network failures are retried after 1, 2 and 4 s (or the server's `Retry-After`). A topic that
  still fails is listed on stderr and left as a `<!-- missing: CONTENT_ID TITLE -->` line in the output, and the run
  exits 1; a 404 is logged and skipped.
- The API path is `/docs/api/khub/` — `/api/khub/` returns 403.
- Every map exists in six locales, and non-English maps often keep English titles. Search keeps only `--lang`
  (default `en-US`) maps; an explicit `--map-id` in another locale triggers a warning.
- Content is © ServiceNow; this tool only automates reading publicly served documentation for personal reference.

## License

MIT — see [LICENSE](LICENSE).
