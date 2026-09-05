---
name: sn-docs-harvester
description: >-
  Download official ServiceNow documentation from servicenow.com/docs as local
  markdown files using the FluidTopics khub API. Use when the user needs to fetch,
  update, refresh, or expand ServiceNow reference docs for any project. Also use
  when the user mentions missing ServiceNow docs, wants to pull docs for a specific
  ServiceNow API or product area (Flow Designer, Integration Hub, CMDB, ATF, CICD,
  etc.), or says things like "download the SN docs for X", "get the latest ServiceNow
  docs", "harvest docs from servicenow.com", or "update the local docs".
---

# ServiceNow Documentation Harvester

Downloads official documentation from servicenow.com/docs via the FluidTopics
khub API. **No authentication required.** Works from plain Python on any surface.

## Prerequisites

- Python 3 (stdlib only — no pip installs required)
- Optional: `pip install html2text` for better markdown conversion
- **claude.ai:** `www.servicenow.com` must be in proxy allowed domains

## API Reference

**Base URL:** `https://www.servicenow.com/docs/api/khub`

> **CRITICAL:** Path is `/docs/api/khub/`, NOT `/api/khub/`.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/docs/api/khub/clustered-search` | Search (body: `{"query":"..."}`) |
| GET | `/docs/api/khub/maps/{mapId}/pages` | TOC (recursive page tree) |
| GET | `/docs/api/khub/maps/{mapId}/topics/{id}/content` | Topic HTML |
| GET | `/docs/api/khub/maps/{mapId}` | Map metadata |
| GET | `/docs/api/khub/locales` | Available languages |

## Usage

```bash
# Search and list maps
python3 scripts/harvest.py --search "CMDB health" --list

# Harvest entire map
python3 scripts/harvest.py --map-id MAP_ID -o output.md -v

# Harvest specific section (recommended for large maps)
python3 scripts/harvest.py --map-id MAP_ID --subtree CONTENT_ID -o output.md -v

# Show TOC tree
python3 scripts/harvest.py --map-id MAP_ID --show-toc
```

## Known Maps

See `references/known-maps.md` for verified mapIds and subtree contentIds.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| 403 | Wrong path `/api/khub/` | Use `/docs/api/khub/` |
| 404 on search | Search is POST | POST to `/docs/api/khub/clustered-search` |
| Blocked in claude.ai | Domain not in proxy | Add `www.servicenow.com` |
