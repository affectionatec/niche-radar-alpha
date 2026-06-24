# Implementation Plan: Agent-Reach Capability Port

> Source PRD: `docs/prd.md` §6 (extensibility)
> Source Spec: `docs/spec/collectors.md`
> Relevant ADRs: ADR-002 (multi-backend fallback)
> Created: 2026-06-24
> Status: In Progress (M1 ships in the first feature PR)

## Overview

Port the capture recipes from [Agent-Reach](https://github.com/Panniantong/Agent-Reach) into Niche Radar **as `SourceBackend`s behind the existing `MultiBackendCollector`** (ADR-002) — never as a wholesale dependency. Agent-Reach is interactive agent-in-a-shell tooling; Niche Radar is an unattended scheduled pipeline. The value is the *curated backend recipes and ordering*, expressed through our `BaseCollector`/`SourceBackend` contract.

**Scope (user-confirmed): comprehensive.** Where a channel already exists, add an alternative backend (harden); where it doesn't, add a new collector. Cookie/ToS-risky paths are last-resort backends only, ordered last, clearly marked (`docs/spec/collectors.md` §6).

**Testing discipline:** every backend is gated by `is_available()`; unit tests mock the network/CLI so CI stays hermetic; live paths need keys/binaries and are marked ⚠️ in handoffs. New runtime deps go in the Dockerfile + an ADR.

## Dependency Graph

```
collectors.md contract (done)
        │
        ▼
M1 Resilience keystone ──> M2 Extra tiers (existing sources)
        │
        ├──> M3 New channels (keyless/native first)
        │            │
        └────────────┴──> M4 Cookie/ToS-risky + partial channels (last)
```

## Critical Path

M1 → (M2 ∥ M3) → M4. Minimum: ~1 session per task.

## Milestones

### M1: Resilience keystone — harden the brittle/quota-bound sources
**Goal:** The 🟠 brittle HTML scrapers and the quota-bound YouTube collector gain resilient backends.
**Demonstrable state:** G2 / Indie Hackers fall through to a Jina path when direct scraping is blocked; YouTube captures transcripts without a Data API key. Tests prove fallthrough; full suite + eval green.

---

#### M1-T1: Shared Jina Reader fetch backend

| Field | Value |
|-------|-------|
| **Builds** | `JinaReaderBackend(SourceBackend)` + a shared `niche_radar/collectors/_jina.py` fetch helper (`r.jina.ai` GET → clean markdown/text) |
| **Depends on** | None |
| **Files** | `niche_radar/collectors/_jina.py`, `niche_radar/collectors/backends/jina.py`, `tests/test_collectors/test_jina_backend.py` |
| **Spec ref** | `docs/spec/collectors.md` §3.3, §6 |
| **Size** | M |

**Acceptance criteria (locked at task start):**
- [ ] `JinaReaderBackend.is_available()` returns False when egress/config absent, never raises — verify: `pytest tests/test_collectors/test_jina_backend.py -k available` exit 0
- [ ] `fetch()` parses a mocked Jina response into normalized raw items with deterministic `source_id` — verify: `pytest tests/test_collectors/test_jina_backend.py -k fetch` exit 0
- [ ] Network is mocked (`responses`/monkeypatch); no live HTTP in tests — verify: test runs offline
- [ ] Full suite ratchet holds — verify: `pytest` count ≥ 371; eval `python -m niche_radar.eval.runner` exit 0
- [ ] Independent verifier returns PASS

---

#### M1-T2: Harden G2 + Indie Hackers with the Jina backend

| Field | Value |
|-------|-------|
| **Builds** | Convert `g2_reviews` and `indie_hackers` to `MultiBackendCollector`: direct-scrape backend first, `JinaReaderBackend` as resilient fallback |
| **Depends on** | M1-T1 |
| **Files** | `niche_radar/collectors/g2_reviews.py`, `niche_radar/collectors/indie_hackers.py`, `tests/test_collectors/test_g2_reviews.py`, `tests/test_collectors/test_indie_hackers.py` |
| **Spec ref** | `docs/spec/collectors.md` §3.2, §5 |
| **Size** | M |

**Acceptance criteria:**
- [ ] When direct scrape is blocked (mocked Cloudflare/403), the chain falls through to Jina and still returns items — verify: `pytest tests/ -k "g2 and fallback"` exit 0
- [ ] `metadata['backends']` records both paths' outcomes — verify: `pytest tests/ -k "g2 and metadata"` exit 0
- [ ] No behavior change when direct scrape succeeds (existing tests pass) — verify: `pytest tests/test_collectors/test_g2_reviews.py` exit 0
- [ ] Suite ratchet + eval green; verifier PASS

---

#### M1-T3: yt-dlp YouTube backend (transcripts, no API quota)

| Field | Value |
|-------|-------|
| **Builds** | `YtDlpBackend(SourceBackend)`; fold YouTube into a `MultiBackendCollector` (Data API backend kept; yt-dlp added for transcript-bearing capture and keyless fallback) |
| **Depends on** | None (parallel with M1-T1/T2) |
| **Files** | `niche_radar/collectors/youtube.py`, `niche_radar/collectors/backends/ytdlp.py`, `tests/test_collectors/test_youtube.py`, `Dockerfile` (add `yt-dlp`) |
| **Spec ref** | `docs/spec/collectors.md` §3.2, §6 |
| **Size** | L |

**Acceptance criteria:**
- [ ] `is_available()` False when the `yt-dlp` binary is absent (never raises) — verify: `pytest tests/test_collectors/test_youtube.py -k available` exit 0
- [ ] `fetch()` maps a mocked `yt-dlp --dump-json` payload (incl. subtitles) into raw items with transcript text in `body` — verify: `pytest tests/ -k "ytdlp and transcript"` exit 0
- [ ] Dockerfile installs `yt-dlp`; absence degrades to the Data API backend, no crash — verify: `pytest tests/ -k "youtube and fallback"` exit 0
- [ ] Suite ratchet + eval green; verifier PASS

---

### M2: Extra fallback tiers for existing resilient sources
**Goal:** Reddit and Twitter/X gain additional capture tiers from Agent-Reach.
**Demonstrable state:** Each source's chain has an added tier that engages when prior tiers are unavailable; tests prove ordering.

---

#### M2-T1: Reddit `rdt-cli`/OpenCLI backend tier

| Field | Value |
|-------|-------|
| **Builds** | `RedditCliBackend` appended behind PRAW + keyless public-JSON |
| **Depends on** | M1-T1 (backend conventions) |
| **Files** | `niche_radar/collectors/reddit.py`, `niche_radar/collectors/backends/reddit_cli.py`, `tests/test_collectors/test_reddit.py` |
| **Spec ref** | `docs/spec/collectors.md` §3.2 |
| **Size** | M |

**Acceptance criteria:**
- [ ] CLI backend used only when PRAW + public-JSON are unavailable/empty — verify: `pytest tests/ -k "reddit and order"` exit 0
- [ ] CLI invocation mocked; no live calls — verify: offline run, exit 0
- [ ] Ratchet + eval green; verifier PASS

---

#### M2-T2: Twitter/X `twitter-cli` backend tier

| Field | Value |
|-------|-------|
| **Builds** | `TwitterCliBackend` inserted into the existing xAI → Xquik → (twitter-cli) → cookie chain, ordered above the cookie last-resort |
| **Depends on** | M1-T1 |
| **Files** | `niche_radar/collectors/twitter.py`, `niche_radar/collectors/x_backends/twitter_cli.py`, `tests/test_collectors/test_twitter*.py` |
| **Spec ref** | `docs/spec/collectors.md` §3.2, §6 |
| **Size** | M |

**Acceptance criteria:**
- [ ] New tier ordered above cookie GraphQL, below key-based paths — verify: `pytest tests/ -k "twitter and order"` exit 0
- [ ] Cookie path remains strictly last-resort — verify: chain-order test, exit 0
- [ ] Ratchet + eval green; verifier PASS

---

#### M2-T3: GitHub `gh` CLI backend (optional, low priority)

Sketch — `GhCliBackend` behind the REST path for higher rate limits when a PAT/`gh` is present. Size S. Detail when scheduled.

---

### M3: New channels — keyless/native first
**Goal:** Add net-new collectors from Agent-Reach that don't require cookies.
**Demonstrable state:** Each new source registered in `ALL_SOURCES`, credential-gated, returns normalized raw items in tests.

- **M3-T1: V2EX collector** — native API, keyless. Size M.
- **M3-T2: 雪球 (Xueqiu) collector** — native API. Size M.
- **M3-T3: Exa global-search collector** — semantic search → raw items (key-gated). Size M.
- **M3-T4: Bilibili collector** — `MultiBackendCollector` (bili-cli → OpenCLI → search API). Size L.
- **M3-T5: 小宇宙 (Xiaoyuzhou) podcast collector** — Whisper transcription; heavy dep, gated. Size L. ⚠️ Risk: Whisper runtime cost — evaluate a hosted-transcription backend first.

> Each M3 task: register in `niche_radar/collectors/__init__.py::ALL_SOURCES`, add `CREDENTIAL_SCHEMA`, spec ref `docs/spec/collectors.md`, mocked-network tests, ratchet + eval green, verifier PASS.

### M4: Cookie/ToS-risky + partial channels (last)
**Goal:** Add the channels that depend on browser cookies / burner accounts — as **last-resort backends only**, clearly marked, with burner-account guidance per Agent-Reach.

- **M4-T1: 小红书 (XiaoHongShu) collector** — OpenCLI/xiaohongshu-mcp/xhs-cli backends, ordered last, ToS-risk noted. Size L. ⚠️
- **M4-T2: LinkedIn collector** — `linkedin-mcp` primary, Jina fallback. Size M. ⚠️

> M4 requires an ADR per channel capturing the ToS/account-risk trade-off before implementation (boundary in `docs/spec/collectors.md` §6).

## Risk Register

| Risk | Impact | Mitigation | Tasks |
|------|--------|------------|-------|
| External CLIs/binaries absent at runtime | Med | `is_available()` gate → fallthrough; install in Dockerfile + ADR | M1-T3, M2-T1/2, M3-T4/5 |
| Live network in CI flakes tests | High | Mock all upstreams (`responses`/monkeypatch); hermetic tests only | all |
| Cookie/burner ToS exposure | High | Last-resort ordering, explicit marking, per-channel ADR | M2-T2, M4 |
| Whisper transcription cost/weight | Med | Prefer hosted-transcription backend; gate heavy local path | M3-T5 |
| Jina/Exa egress blocked in some envs | Low | `is_available()` checks egress; degrade to prior backend | M1-T1, M3-T3 |

## Parallelization Opportunities

- M1-T1, M1-T3 independent (different files) — parallelizable via worktrees.
- M3-T1, M3-T2, M3-T3 are independent new collectors.

> Parallel agents: one worktree + one branch + one draft PR per task, merging through the verification gate (→ git-workflow). Tasks touching the same file (e.g., `__init__.py::ALL_SOURCES`) must serialize.

## Rollback Points

- After M1: resilience added with zero new sources — safe to pause; pure hardening.
- After M2: existing sources strengthened — can defer all new-channel work (M3/M4) if scope tightens.
