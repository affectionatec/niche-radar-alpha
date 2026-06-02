<!-- generated: 2026-06-02 -->
# Integration Plan: `last30days` Capture Engine → Niche Radar Collectors

> **Goal of this document.** Distil how the [`last30days`](https://github.com/mvanhorn/last30days-skill)
> skill captures information from mainstream platforms, and lay out a concrete,
> phased plan to fold those capture techniques into Niche Radar's collector
> layer. Two outcomes are prioritised:
>
> 1. **Expandable data sources** — make adding a new platform a small, uniform
>    change rather than a bespoke collector.
> 2. **More stable capture, especially X/Twitter** — replace our single-path,
>    "very brittle" X collector with a multi-backend fallback chain modelled on
>    `last30days`.
>
> This is a planning document. No collector code is changed by this PR.

---

## 1. Executive summary

`last30days` is a research skill (v3.3.1) whose real engine is a Python package
under `skills/last30days/scripts/`. It pulls recent posts and engagement from
**17+ platforms** (Reddit, X, YouTube, TikTok, Instagram, Hacker News,
Polymarket, GitHub, Bluesky, TruthSocial, Threads, Pinterest, Xiaohongshu,
Digg, Perplexity grounding, plus web search). Its durability comes from three
architectural choices that Niche Radar currently lacks:

| `last30days` pattern | What it buys | Niche Radar today |
|----------------------|--------------|-------------------|
| **Per-source module with a uniform `search_*` / `parse_*_response` contract** | New sources are drop-in; one file per platform | Each collector is bespoke; shared contract is only `BaseCollector` |
| **Multi-backend fallback chains per source** (esp. X: xAI → Bird/GraphQL → xurl → Xquik → web) | A source stays "up" even when one backend breaks | Single backend per source; X has exactly one path |
| **Resilient stdlib HTTP layer** (DNS-aware retry, 429-specific cap, anti-bot HTML-interstitial detection, secret redaction) | Transient failures self-heal; logs are safe | `requests` + ad-hoc `tenacity` per collector |

The highest-leverage adoption for us is the **X multi-backend chain** — it
directly targets the "🔴 Very Brittle" rating in our README. The second is the
**source-module contract**, which makes "expand the data sources" a routine
task.

---

## 2. Source-repo architecture (deep dive)

### 2.1 Engine layout

```
skills/last30days/scripts/
├── last30days.py            # CLI entry / orchestrator (1.4k+ lines)
├── lib/
│   ├── http.py              # stdlib-only HTTP w/ retry, 429 cap, DNS backoff, secret redaction
│   ├── env.py               # layered credential resolution (env > .env file > Keychain > Codex)
│   ├── providers.py         # LLM provider catalog (Gemini/OpenAI/xAI/OpenRouter)
│   ├── preflight.py         # query-quality gate (keyword-trap refusal)
│   ├── pipeline.py          # fan-out orchestration + per-source dispatch (the switchboard)
│   ├── fanout.py            # concurrent source fan-out
│   ├── fusion.py            # weighted reciprocal-rank fusion across sources
│   ├── dedupe.py / cluster.py / rerank.py / relevance.py   # post-capture processing
│   │
│   ├── reddit*.py (7 files) # multi-strategy Reddit: public, RSS, listing, shreddit, keyless, enrich, SC API
│   ├── bird_x.py            # X via vendored GraphQL client (Node)  ─┐
│   ├── xai_x.py             # X via xAI Agent Tools API              ├─ X backends
│   ├── xurl_x.py            # X via official API v2 (OAuth2/xurl CLI)│
│   ├── xquik.py             # X via Xquik REST API                  ─┘
│   ├── youtube_yt.py        # YouTube via yt-dlp + ScrapeCreators fallback
│   ├── tiktok.py / instagram.py / threads.py / pinterest.py  # ScrapeCreators-backed
│   ├── bluesky.py           # Bluesky AT Protocol (app password)
│   ├── truthsocial.py       # TruthSocial (token)
│   ├── polymarket.py        # Polymarket (keyless)
│   ├── hackernews.py        # HN Algolia/Firebase (keyless)
│   ├── github.py            # GitHub (token or gh CLI)
│   ├── digg.py              # Digg (CLI)
│   ├── xiaohongshu_api.py   # Xiaohongshu (self-hosted API base)
│   ├── perplexity.py        # Perplexity Sonar grounding (OpenRouter)
│   └── grounding.py         # web search (Brave/Exa/Serper/Parallel)
└── lib/vendor/bird-search/  # vendored @steipete/bird v0.8.0 (MIT), Node.js GraphQL client
```

### 2.2 The per-source module contract

Every source module exposes the same shape, which is what makes the set
expandable:

- `DEPTH_CONFIG = {"quick": …, "default": …, "deep": …}` — controls how many
  calls / results per run.
- `expand_<source>_queries(topic, depth) -> list[str]` — generates query
  variants locally (no LLM needed).
- `search_<source>(query, from_date, to_date, depth=…, token=…) -> dict` —
  performs capture, returns raw JSON-ish dict (never raises for "no results";
  returns `{"items": [], "error": …}` on failure).
- `parse_<source>_response(raw, …) -> list[dict]` — normalises to a common item
  shape (text/url/author/date/engagement/relevance).

`pipeline.py` is a switchboard: `available_sources(config)` decides which
sources are reachable given the current credentials, and a big `if source ==
"…":` dispatch calls the matching `search_*`/`parse_*` pair. Adding a source =
add a module + one dispatch branch + one availability check.

### 2.3 Resilient HTTP layer (`lib/http.py`, stdlib only)

Worth porting almost verbatim. Key behaviours:

- **DNS-failure awareness** — `socket.gaierror` gets a dedicated minimum retry
  count (`MIN_DNS_RETRIES`) with exponential backoff (1s/2s/4s), separate from
  ordinary retries.
- **Separate 429 cap** (`MAX_429_RETRIES`) so rate-limit storms don't burn the
  whole retry budget.
- **Secret redaction in logs** — URLs are regex-scrubbed
  (`key|api_key|token|secret` → `***`) before logging.
- No third-party dependency (pure `urllib`), so it can't break on a transitive
  upgrade.

### 2.4 Layered credential resolution (`lib/env.py`)

Credentials resolve in priority order: **process env → `.env` config file →
macOS Keychain → Codex auth file**. A single `KEYCHAIN_KEYS` tuple is the
source of truth for what's looked up. This matters for us because Niche Radar
stores credentials per-source in SQLite (`get_source_credential`) — the
*concept* of "try several credential sources in priority order" is the part to
borrow, even though our storage differs.

### 2.5 Query-quality pre-flight (`lib/preflight.py`)

Before spending API calls, demographic "keyword-trap" queries (e.g. *"birthday
gift for 40 year old"*) are refused with a structured message, because the
literal phrase isn't how people actually post. Relevant to A-side quality but
**out of scope** for the capture-stability goal; noted for completeness.

---

## 3. Capture-script inventory

Full inventory of `last30days` capture modules, the method each uses, auth
requirements, and observed stability characteristics. The "Auth" column is the
deciding factor for what we can adopt without new paid dependencies.

| Module | Platform | Capture method | Auth | Runtime dep | Stability |
|--------|----------|----------------|------|-------------|-----------|
| `reddit_public.py` | Reddit | Public JSON endpoints | None | — | 🟢 |
| `reddit_rss.py` | Reddit | Search RSS feed | None | — | 🟢 |
| `reddit_listing.py` | Reddit | Listing-card HTML | None | — | 🟡 |
| `reddit_shreddit.py` | Reddit | Shreddit comment HTML | None | — | 🟡 |
| `reddit.py` (SC) | Reddit | ScrapeCreators REST | `SCRAPECREATORS_API_KEY` | — | 🟢 |
| **`xai_x.py`** | **X** | xAI Agent Tools live X search | `XAI_API_KEY` | — | 🟢 |
| **`bird_x.py`** | **X** | Internal GraphQL (vendored bird) | `AUTH_TOKEN`+`CT0` cookies | Node.js | 🟡 |
| **`xurl_x.py`** | **X** | Official API v2 search/recent | OAuth2 (free dev app) | `xurl` CLI | 🟢 |
| **`xquik.py`** | **X** | Xquik REST API | `XQUIK_API_KEY` | — | 🟢 |
| `youtube_yt.py` | YouTube | yt-dlp + SC fallback | None / SC key | `yt-dlp` | 🟢 |
| `tiktok.py` | TikTok | ScrapeCreators REST | SC key | — | 🟢 |
| `instagram.py` | Instagram | ScrapeCreators REST | SC key | — | 🟢 |
| `threads.py` | Threads | ScrapeCreators REST | SC key | — | 🟡 |
| `pinterest.py` | Pinterest | ScrapeCreators REST | SC key | — | 🟡 |
| `bluesky.py` | Bluesky | AT Protocol search | App password (optional) | — | 🟢 |
| `truthsocial.py` | TruthSocial | Public/token API | Token (optional) | — | 🟡 |
| `polymarket.py` | Polymarket | Public Gamma API | None | — | 🟢 |
| `hackernews.py` | Hacker News | Algolia + Firebase | None | — | 🟢 |
| `github.py` | GitHub | REST + gh CLI fallback | Token (optional) | `gh` (opt) | 🟢 |
| `digg.py` | Digg | `digg-pp-cli` | None | CLI | 🟡 |
| `xiaohongshu_api.py` | Xiaohongshu | Self-hosted API base | API base URL | — | 🟡 |
| `perplexity.py` | Web (Sonar) | Perplexity via OpenRouter | `OPENROUTER_API_KEY` | — | 🟢 |
| `grounding.py` | Web | Brave/Exa/Serper/Parallel | Any one key | — | 🟢 |

### 3.1 The X stability story (the crown jewel)

`last30days` treats "search X" as an **ordered fallback chain**, not a single
call. From `env.get_x_source()`:

```
priority:  explicit pin (LAST30DAYS_X_BACKEND)
        →  xAI API            (XAI_API_KEY present)
        →  Bird / GraphQL     (AUTH_TOKEN + CT0 cookies present, Node installed)
        →  xurl / official v2 (xurl CLI installed & authenticated)
        →  (none → web-only grounding fallback)
```

On top of the *backend* fallback, `bird_x.search_x()` adds **query-level
retries** when a backend returns zero results:

1. Literal query `"<core> since:<date>"`.
2. OR-group of compound terms: `("multi-agent" OR "agent simulation") since:…`.
3. Fewer keywords (first two tokens).
4. Single strongest token (longest non-stopword — usually the product name).

And `bird_x._run_bird_search()` adds **anti-bot resilience**: when X's edge
serves an HTML interstitial instead of JSON, it detects the non-JSON/HTML
shape, logs it distinctly from "no results", and retries the subprocess
(`MAX_JSON_DECODE_RETRIES`, `JSON_DECODE_RETRY_DELAY`).

**This three-layer design (backend chain → query retries → anti-bot retry) is
exactly what our X collector is missing.**

---

## 4. Gap analysis vs Niche Radar

Niche Radar (`niche_radar/collectors/`) has 12 collectors behind a clean
`BaseCollector` (`collect()` + `test_connection()` → `CollectorResult`),
registered in `collectors/__init__.py::ALL_SOURCES`, with credentials in SQLite
via `get_source_credential`. Items normalise to
`{source_id, title, body, url, score, comment_count, metadata, posted_at}`.

| Aspect | `last30days` | Niche Radar | Gap / opportunity |
|--------|--------------|-------------|-------------------|
| X/Twitter | 4 backends + query/anti-bot retries | **1 backend** (`twitter.py`: GraphQL cookie via `twikit` transaction-id + query-id scraping) | **Single point of failure.** Add backend chain. |
| Reddit | 7 strategies, public-first | PRAW (official API) | Ours is already 🟢; could add keyless public fallback for resilience. |
| Source count | 17+ platforms | 12 collectors | Missing: TikTok, Instagram, Bluesky, TruthSocial, Polymarket, Threads, Pinterest, Digg, Perplexity/web-grounding. |
| HTTP resilience | stdlib, DNS+429-aware, secret redaction | per-collector `requests`/`tenacity` | Centralise a resilient client. |
| Add-a-source cost | module + dispatch + availability | bespoke collector class | Adopt a thin source-module convention under `BaseCollector`. |
| Backend fallback | first-class (`get_x_source`) | none | Generalise a "strategy chain" base. |

### 4.1 Why our current X collector is brittle (concretely)

`niche_radar/collectors/twitter.py` depends on a chain of fragile assumptions,
each of which is a documented failure mode in its own header comment:

- Scrapes `x.com/` homepage + `ondemand.s` chunk to build a valid
  `x-client-transaction-id` (regexes against minified JS that X changes).
- Scrapes `main.js` for the live `SearchTimeline` query ID (falls back to a
  hard-coded `_DEFAULT_QUERY_ID` that goes stale).
- Hard-codes a large `_FEATURES` dict that X periodically changes (→ HTTP 400).
- Requires valid `ct0` + `auth_token` cookies that expire and must be
  re-copied by hand.
- Any one of these breaking takes the **entire** X source down — there is no
  alternative path.

---

## 5. Target integration architecture

### 5.1 Principle: a collector is a *chain of backends*

Introduce a `MultiBackendCollector` (subclass of `BaseCollector`) that owns an
ordered list of "backends", each implementing a tiny interface:

```python
class SourceBackend(Protocol):
    name: str
    def is_available(self, settings, db) -> bool: ...      # credentials/binaries present?
    def fetch(self, query, since, settings, db) -> list[dict]: ...  # normalized items; never raises for "empty"
```

`MultiBackendCollector.collect()` walks the chain in priority order, calling the
first *available* backend; on failure or empty result it falls through to the
next, recording per-backend status in `CollectorResult.metadata`. This is the
`get_x_source()` pattern generalised, and it makes every source resilient — not
just X.

```
TwitterCollector(MultiBackendCollector):
    backends = [
        XaiBackend,        # XAI_API_KEY            (zero scraping, most stable)
        XurlBackend,       # official API v2        (OAuth2, free dev app)
        XquikBackend,      # XQUIK_API_KEY          (REST, full engagement)
        GraphQLCookieBackend,  # current twitter.py path (last resort)
        # → if all unavailable, source is simply skipped (status="failed", clear message)
    ]
```

This **inverts our current risk**: the brittle GraphQL-cookie path becomes the
*last* resort instead of the *only* path.

### 5.2 Mapping `last30days` modules onto our `BaseCollector`

Each `lib/<source>.py` maps to one backend. The translation is mechanical:

| `last30days` | Niche Radar backend | Notes |
|--------------|---------------------|-------|
| `xai_x.search_x` + `parse_x_response` | `XaiBackend.fetch` | Reuse the prompt; map items → our item dict |
| `xurl_x.search_x` + `parse_x_response` | `XurlBackend.fetch` | Requires `xurl` CLI; `is_available` = `xurl whoami` ok |
| `xquik.search_xquik` + `parse_xquik_response` | `XquikBackend.fetch` | Pure REST; cleanest new dependency |
| `bird_x` (Node) | *optional* | Heaviest (needs Node + vendored client); consider porting query-retry/anti-bot logic into our existing Python GraphQL path instead |
| `tiktok/instagram/threads/pinterest` | new `*Collector` (ScrapeCreators) | One SC key unlocks four sources |
| `bluesky` | new `BlueskyCollector` | AT Protocol, app-password optional |
| `polymarket` / `hackernews`(already) | new `PolymarketCollector` | Keyless, 🟢 |
| `perplexity`/`grounding` | web-validation backend for agent A3 | Complements existing web validation |

The normalisation step is small: `last30days` items carry
`text/url/author_handle/date/engagement{likes,reposts,replies}` → our
`{title (text[:140]), body (text), url, score (likes+reposts), comment_count
(replies), posted_at (date), metadata}`.

### 5.3 Shared resilient HTTP client

Port `lib/http.py` to `niche_radar/collectors/_http.py` (or wrap `httpx`,
already a dependency, with the same policies): DNS-aware retry, 429-specific
cap, exponential backoff, and **secret redaction in structlog output**. All new
backends use it; existing collectors migrate opportunistically.

---

## 6. Phased roadmap

Each phase is independently shippable and leaves the system working.

### Phase 0 — Foundations (no new sources)
- Add `MultiBackendCollector` base class + `SourceBackend` protocol.
- Add the shared resilient HTTP client (port of `lib/http.py` policies).
- Add per-backend status to `CollectorResult.metadata` and surface it on the
  dashboard's source-health view.
- **Exit criteria:** existing 12 collectors unchanged in behaviour; new base
  class covered by unit tests with a fake 2-backend source.

### Phase 1 — Stabilise X (the headline win) 🔴→🟢
- Refactor `TwitterCollector` to `MultiBackendCollector`.
- Implement `XaiBackend`, `XurlBackend`, `XquikBackend` (ported from
  `xai_x`/`xurl_x`/`xquik`).
- Demote the existing GraphQL-cookie logic to `GraphQLCookieBackend` (last
  resort) and fold in the **query-level retries** (OR-groups, keyword
  reduction, strongest-token) and **anti-bot HTML-interstitial retry** from
  `bird_x`.
- Update `Settings → Data Sources → Twitter` to configure any/all of:
  `XAI_API_KEY`, `xurl` OAuth, `XQUIK_API_KEY`, cookie pair — with a clear
  "active backend" indicator (port `get_x_source_status`).
- **Exit criteria:** with `XAI_API_KEY` *or* `XQUIK_API_KEY` set, X capture
  succeeds with **zero cookie/scraping dependency**; README reliability for X
  moves off 🔴.

### Phase 2 — Expand low-friction, keyless/cheap sources
- `PolymarketCollector` (keyless), Bluesky (`BlueskyCollector`, app-password
  optional). Both 🟢 and additive.
- **Exit criteria:** two new sources in `ALL_SOURCES`, each with
  `test_connection` and dashboard health rows.

### Phase 3 — ScrapeCreators source family
- One `SCRAPECREATORS_API_KEY` unlocks TikTok, Instagram, Threads, Pinterest.
  Add as four collectors sharing a small SC client.
- **Exit criteria:** sources gated on key presence; gracefully absent when
  unset.

### Phase 4 — Web grounding for validation
- Wire `grounding`/`perplexity` style web search into Agent A3 (Market
  Researcher) validation, behind any one of Brave/Exa/Serper/Parallel/OpenRouter
  keys.
- **Exit criteria:** A3 web-validation has a pluggable backend; no hard
  dependency on a single search provider.

### Phase 5 — Reddit resilience (optional)
- Add a keyless public-first Reddit backend as a fallback under PRAW, mirroring
  `reddit_public`/`reddit_rss`, so Reddit survives API-credential issues.

---

## 7. Dependencies, licensing & credentials

- **Licensing:** `last30days` is **MIT**; the vendored `bird-search` is
  `@steipete/bird` v0.8.0, also **MIT**. We may port/adapt code with attribution
  (retain license headers). Prefer *porting techniques* over copying large
  files where practical.
- **New runtime deps (all optional, gated on credentials):**
  - `XaiBackend` — HTTP only (no new dep).
  - `XquikBackend` — HTTP only; needs `XQUIK_API_KEY` (paid).
  - `XurlBackend` — needs the `xurl` CLI installed + OAuth2 login (free X dev
    app).
  - `bird_x` (if adopted) — needs **Node.js** + vendored client. Heaviest;
    recommend deferring in favour of porting its retry logic into Python.
  - ScrapeCreators family — `SCRAPECREATORS_API_KEY` (paid, one key covers 4).
- **Credential storage:** keep our SQLite `get_source_credential` model; add
  new keys to each collector's `CREDENTIAL_SCHEMA` so they appear in
  `Settings → Data Sources`. No `.env`-file or Keychain layering required for
  v1 (that's a `last30days` desktop concern).
- **`.env.example`:** add commented stubs — `XAI_API_KEY`, `XQUIK_API_KEY`,
  `SCRAPECREATORS_API_KEY`, `BSKY_HANDLE`/`BSKY_APP_PASSWORD` — clearly marked
  optional.
- **Secret hygiene:** adopt `lib/http.py`'s URL secret-redaction before logging,
  since several new backends carry keys in query strings.

---

## 8. Risks & open questions

1. **Paid backends.** xAI/Xquik/ScrapeCreators are paid. The chain design means
   they're optional — but the *most stable* X paths cost money. The free-but-
   fragile cookie path remains as last resort. **Decision needed:** which paid
   backend (if any) is the recommended default for X?
2. **`xurl` is the best free+stable X option** (official API v2, OAuth2) but
   needs a CLI binary and a one-time dev-app login — awkward inside Docker.
   **Open question:** bundle `xurl` in the image, or document host setup?
3. **Node.js for `bird_x`.** Adds image weight and a second runtime. Recommended
   stance: **do not vendor bird**; instead port its query-retry + anti-bot-retry
   logic into our existing Python GraphQL path. Revisit only if a pure-Python
   GraphQL path proves insufficient.
4. **Rate limits & politeness.** `last30days` paces requests (`time.sleep`
   between queries) and caps X fetches (`MAX_SOURCE_FETCHES = {"x": 2}`). Carry
   these caps over to respect platform limits within our 4h collection cycle.
5. **Scope creep into ranking.** `last30days` also ships fusion/rerank/relevance
   — Niche Radar already has its own A1–A8 pipeline + clustering, so we should
   integrate **capture only** and not its synthesis layer.

---

## 9. Recommended first PR (after this plan is approved)

Phase 0 + the `XquikBackend`/`XaiBackend` slice of Phase 1, because:
- it's pure-HTTP (no Node, no CLI), so it lands cleanly in Docker;
- it immediately gives X a stable path that needs **no cookies and no
  scraping**; and
- it exercises the `MultiBackendCollector` base end-to-end, de-risking every
  later source addition.

---

### Appendix A — Key source references

| Concept | File in `last30days` |
|---------|----------------------|
| X backend priority resolution | `lib/env.py::get_x_source` / `get_x_source_status` |
| X per-source dispatch | `lib/pipeline.py` (`if source == "x":`) |
| X query-level retries | `lib/bird_x.py::search_x` |
| Anti-bot HTML-interstitial retry | `lib/bird_x.py::_run_bird_search` |
| xAI live-search prompt + parse | `lib/xai_x.py` |
| Official API v2 path | `lib/xurl_x.py` |
| Xquik REST path | `lib/xquik.py` |
| Resilient HTTP policies | `lib/http.py` |
| Layered credential resolution | `lib/env.py` |
| Source availability gating | `lib/pipeline.py::available_sources` |

### Appendix B — Niche Radar touch-points

| Concept | File in Niche Radar |
|---------|---------------------|
| Collector contract | `niche_radar/collectors/base.py` |
| Source registry | `niche_radar/collectors/__init__.py` (`ALL_SOURCES`, `_get_collector`) |
| Current X collector | `niche_radar/collectors/twitter.py` |
| Credential storage | `niche_radar/storage/repository.py::get_source_credential` |
| Item normal form | `upsert_raw_item` args in `collectors/__init__.py` |
