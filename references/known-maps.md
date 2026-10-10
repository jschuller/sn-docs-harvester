# Known ServiceNow Documentation Maps

All IDs below are en-US maps. Australia/Zurich/Yokohama sections verified 2026-03-24.

## Platform Capabilities (by release)
| Release | mapId |
|---------|-------|
| Australia | q4dSP2Icgr1SFv5wanVXvQ |
| Zurich | zS6yb8e~gR8BPjeviYdV9g |
| Yokohama | Ir~NPf1dr8MGFXQE6QlBoQ |

## Key Subtrees (Australia)
| Section | contentId | Topics |
|---------|-----------|--------|
| CMDB | TWapvFkBRG6eQTu7R3FYQw | 499 |
| CSDM | UM3GV9yG5VLzKkb8PTUMKQ | 60 |
| 3rd-party CMDB integration | HHJL4R5mpTc9rYpFLDdxtA | 268 |


## Locales

Every map is published in six locales (en-US, fr-FR, de-DE, ja-JP, ko-KR, pt-BR) with different mapIds, and many
non-English Brazil maps keep English titles, so a title alone does not tell you the language. `harvest.py` filters
search results to `--lang` (default `en-US`) and warns when an explicit `--map-id` is in another locale.
Check a map with `GET /docs/api/khub/maps/{mapId}` → `lang`.

## Brazil (en-US, verified 2026-10-10)

| Map | mapId |
|-----|-------|
| Build or modify applications | C4bUYQp3V4MvsELLhAZSXg |
| API Reference | ooCZhg2g6YDYvKp3oBwAxA |
| Release Notes | 97F4kxpjkdv178Iq1OQ9sQ |
| Delta Australia → Brazil (Combined Product Files) | iEKwGum3qMhhbQyT8u5vLA |
| Delta Zurich → Brazil | 9MRxcKWk2bUT4w5Vb5ZxVg |
| ServiceNow AI Platform Capabilities | zf4CFrQ4oaR8UN3GV4kT5g |
| Platform security | V4HkxYleMr32qwc1nHrCsQ |
| Enable AI | UBGwc5glUUjVANqQeiJeZA |

### Key Subtrees (Brazil)
| Map | Section | contentId | Topics |
|-----|---------|-----------|--------|
| Build or modify applications | Building applications in source code | 4B05VSybJXmD51o83dEpsg | 90 |
| Build or modify applications | ServiceNow SDK | oIcm5XzG4iQ67u0tqkIWNA | 48 |
| Build or modify applications | ServiceNow SDK CLI | tzU6HlTYxFiKxTeNH3E2QA | 1 |
| Build or modify applications | ServiceNow Fluent API reference | rM5SN2lWLtNHvtenWMXfEQ | 27 |
| Build or modify applications | ServiceNow IDE | C2VY7Rz52jrMtHM7iGOFYA | 36 |
| Build or modify applications | ServiceNow Studio | 4MhwhswptxkIidXaHTKBQA | 107 |
| Build or modify applications | Build Agent | J4p7gKS~s0HTxLNF9zi6cg | 40 |
| Build or modify applications | Agentic development | WE7d95heVf4DZTnmsspmcg | 26 |
| Build or modify applications | Automated Test Framework (ATF) | 0jVTNQj7sx7oK1YLwkV0Gg | 182 |
| Build or modify applications | ATF Test API (Fluent) | qqpfLlF95RuiDl4j1pVeOg | 1 |
| Build or modify applications | Application access settings | mss_W5JrRuBSM76JjFlYaQ | 25 |
| Build or modify applications | Application scope | qSvn~aP_IoH6d8LGkwvbzw | 4 |
| Build or modify applications | Cross-Scope Privilege API (Fluent) | uOf_m6j86cenlBs9gtXpUA | 1 |
| Build or modify applications | Application Runtime Policy (ARP) | ot6R6AIWhVzIFpxd5I~a1g | 17 |
| API Reference | REST API reference | keRK4IL_S4WbT0HjSHbo2A | 141 |
| API Reference | CICD API | MiRJEjvczFfKK_do0BOLrQ | 1 |
| API Reference | CICD Update Set API | PQeRZrvwdhHI_fl1ALl0XQ | 1 |
| API Reference | Table API | 7w1JJoLZD0npie7B6i9GEw | 1 |
| API Reference | Scripted REST APIs | nRiUzqlF84WMnhXXIqXaDg | 26 |
| Release Notes | Release notes for upgrading from Australia | N8GClubcylcGIoC5VYCmNQ | 260 |
| Release Notes | App development and low-code release notes | HvQjGum61Vz9O_wRSjBXWw | 28 |
| Release Notes | API release notes | XQaHRy26x3S9bAIvpE4kAw | 1 |
| Release Notes | ServiceNow AI Platform security release notes | fs7mmlB2Qm81d2uTqDbcog | 12 |
| Delta Australia → Brazil | Combined ServiceNow SDK release notes (Australia → Brazil) | S1aOY5kJ_QYmu5sOsImwkw | 1 |
| Platform Capabilities | CMDB | C9rzCm3a1kXrkG22cMlAgw | 504 |
| Platform Capabilities | CSDM | mHB22ygzCJj8Vo~h0561Ig | 60 |
| Platform Capabilities | Integrating third-party data into CMDB | kb_QCF4pKBXjaFBxakdUaA | 328 |

The CICD API is one large page; harvest it with `--timeout 180`.

## Search for more
```bash
python3 scripts/harvest.py --search "Flow Designer" --list
```
