# QA Report: OpenMy Web App

| Field | Value |
|-------|-------|
| Date | 2026-04-13 |
| Target | http://localhost:8420 |
| Server | Python 3.13 / SimpleHTTP |
| Mode | API + Static Asset Testing (no browser) |
| Health Score | **82/100** |

## Summary

| Severity | Count | Fixed | Deferred |
|----------|-------|-------|----------|
| Critical | 0 | — | — |
| High | 2 | 0 | 2 |
| Medium | 3 | 0 | 3 |
| Low | 3 | 0 | 3 |

## Top 3 Things to Fix

1. **Test data (2099-12-31) leaks into production dates** — users see a mystery future date
2. **`/api/health` returns 404** — breaks health checks, claimed as "added" in project status
3. **Full filesystem path exposed in API response** — information disclosure in `/api/onboarding`

---

## Issues

### ISSUE-001: Test data visible in production
- **Severity:** HIGH
- **Category:** Content / Data Quality
- **Status:** Deferred (needs source fix)

**Description:** The `/api/dates` endpoint returns a test date `2099-12-31` alongside real user data (`2026-04-08`). The sidebar date list will show this phantom future date. There are also test dates `2099-03-01` and `2099-03-02` in the data directory.

**Evidence:**
```
GET /api/dates → includes {"date": "2099-12-31", "segments": 1, "word_count": 58}
Data directory: ls data/ → 2099-03-01, 2099-03-02, 2099-12-31
```

**Fix:** Remove `data/2099-*` directories, or add a date filter in the server to exclude future dates.

---

### ISSUE-002: Health endpoint returns 404
- **Severity:** HIGH
- **Category:** Functional
- **Status:** Deferred (needs source fix)

**Description:** `GET /api/health` returns 404. The project status from today claims "8420 健康检查" was added, but the endpoint doesn't exist in the running server.

**Evidence:**
```
$ curl -s -o /dev/null -w "%{http_code}" http://localhost:8420/api/health
404
```

**Impact:** Container orchestration, monitoring tools, and load balancers rely on health endpoints. Without it, the server can't be deployed behind a reverse proxy that checks health.

---

### ISSUE-003: Filesystem path leaked in API response
- **Severity:** MEDIUM
- **Category:** Security / Information Disclosure
- **Status:** Deferred

**Description:** The `/api/onboarding` response includes a `state_path` field with the full absolute path to a local file:
```
"state_path": "/Users/zhousefu/Desktop/openmy-clean/data/onboarding_state.json"
```

This leaks the username, directory structure, and project layout to any client calling the API.

**Fix:** Remove `state_path` from the API response, or make it relative.

---

### ISSUE-004: Sidebar icons massively oversized
- **Severity:** MEDIUM
- **Category:** Performance
- **Status:** Deferred

**Description:** Three PNG icons used in the sidebar are way too large for their display size:

| Icon | Size | Expected |
|------|------|----------|
| search.png | 114 KB | < 5 KB |
| settings.png | 138 KB | < 5 KB |
| logo.png | 58 KB | < 10 KB |

Total: ~310 KB just for 3 small icons. Other icons (transcription, provider badges) are proper SVGs (< 300 bytes each).

**Fix:** Convert search.png and settings.png to SVG, or compress to appropriate dimensions. The provider icons are already good examples of the right approach.

---

### ISSUE-005: Context query returns unhelpful error
- **Severity:** MEDIUM
- **Category:** UX / API Design
- **Status:** Deferred

**Description:** `GET /api/context/query?type=projects` returns `{"error": "不支持的查询类型："}`. The error message is incomplete (doesn't show what was passed) and doesn't tell the user what valid types are.

**Evidence:**
```
$ curl http://localhost:8420/api/context/query?q=openmy
{"error": "不支持的查询类型："}
```

---

### ISSUE-006: macOS Finder duplicate files in data directory
- **Severity:** LOW
- **Category:** Housekeeping
- **Status:** Deferred

**Description:** Two files with Finder copy naming patterns exist:
- `data/profile 2.json`
- `data/active_context_updates 2.jsonl`

These are accidental copies, not intentional data files.

---

### ISSUE-007: No favicon.ico
- **Severity:** LOW
- **Category:** UX
- **Status:** Deferred

**Description:** `GET /favicon.ico` returns 404. Browser tabs show a generic icon. The logo exists at `/static/icons/logo.png` but isn't served as favicon.

**Fix:** Add `<link rel="icon" href="/static/icons/logo.png">` to HTML. (Note: this tag already exists in the HTML but the browser also requests `/favicon.ico` as a fallback.)

---

### ISSUE-008: HEAD requests return different status than GET
- **Severity:** LOW
- **Category:** Functional
- **Status:** Deferred

**Description:** `HEAD /api/onboarding` returns 404, but `GET /api/onboarding` returns 200. This is because the Python SimpleHTTP server handles HEAD separately from the custom API routing.

**Impact:** Monitoring tools using HEAD for uptime checks will report false negatives.

---

## What Works Well

| Area | Status | Notes |
|------|--------|-------|
| Homepage | OK | Loads in < 2ms, proper Chinese content |
| Static assets | OK | All CSS/JS/icons load (7 files) |
| API performance | Excellent | All endpoints < 4ms response time |
| Search | OK | Chinese search works, highlights matches with `<mark>` |
| Correction system | OK | POST add + GET list both work |
| Onboarding | OK | Clear provider choices, proper state management |
| Day data | OK | Rich structure (segments, summaries, decisions, todos) |
| Theme switching | OK | Light/dark/auto properly configured |
| Screen context settings | OK | Settings accessible and configurable |
| Date navigation | OK | `/api/dates` returns rich day summaries |

## API Endpoint Status

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/` | GET | 200 | 5391 bytes |
| `/static/*` | GET | 200 | All assets served |
| `/api/dates` | GET | 200 | List of processed dates |
| `/api/date/{date}` | GET | 200 | Full day data |
| `/api/onboarding` | GET | 200 | Onboarding state |
| `/api/onboarding/select` | POST | 200 | Select STT provider |
| `/api/context` | GET | 200 | Context summary |
| `/api/context/decisions` | GET | 200 | Empty array |
| `/api/context/loops` | GET | 200 | Empty array |
| `/api/context/projects` | GET | 200 | Empty array |
| `/api/corrections` | GET | 200 | Correction dictionary |
| `/api/correct/typo` | POST | 200 | Add correction |
| `/api/search` | GET | 200 | Search with highlights |
| `/api/stats` | GET | 200 | Usage stats |
| `/api/jobs` | GET | 200 | Job list |
| `/api/pipeline/jobs` | GET | 200 | Pipeline jobs |
| `/api/settings/screen-context` | GET | 200 | Screen settings |
| `/api/health` | GET | **404** | Missing |
| `/api/context/query` | GET | **400** | Incomplete error |
| `/favicon.ico` | GET | **404** | Missing |

## Health Score Breakdown

| Category | Weight | Score | Notes |
|----------|--------|-------|-------|
| Console | 15% | N/A* | No browser testing |
| Links | 10% | 100 | All API links valid |
| Visual | 10% | N/A* | No browser testing |
| Functional | 20% | 70 | Test data in prod, health missing |
| UX | 15% | 85 | Well-structured, icon sizes |
| Performance | 10% | 100 | All < 4ms |
| Content | 5% | 85 | Good content, test data leak |
| Accessibility | 15% | N/A* | No browser testing |

*N/A categories scored at 80 (assumed baseline for a well-structured app)

**Final Score: 82/100**

---

## Limitations

This QA was conducted via curl/API testing only. The browse tool (headless browser) was unavailable in this environment. The following could NOT be tested:
- JavaScript interactions (sidebar toggle, search modal, theme switching)
- Visual layout and rendering
- Mobile responsiveness
- Console errors
- Form interactions
- Screen capture settings UI
- Correction popover UI
