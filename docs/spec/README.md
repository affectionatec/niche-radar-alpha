# Technical Specifications — Index

Bounded-context specs for Niche Radar. One spec per domain; no monolith. These decompose the original `docs/spec.md` (which remains as a detailed historical reference until decomposition completes — ADR-004).

| Spec | Domain | Status | Source of truth for |
|------|--------|--------|---------------------|
| [collectors.md](collectors.md) | Data-source ingestion & multi-backend capture | **Approved** | `BaseCollector`, `CollectorResult`, `MultiBackendCollector`/`SourceBackend`, the raw-item contract |
| [analysis-pipeline.md](analysis-pipeline.md) | 8-agent LLM analysis (A1–A8) + clustering | Draft (consolidating) | Agent I/O contracts, clustering, budget cap |
| [api.md](api.md) | FastAPI surface + job control | Draft (consolidating) | HTTP endpoints, settings, pipeline jobs |
| [storage.md](storage.md) | SQLite/PostgreSQL schema & retention | Draft (consolidating) | Tables, invariants, cleanup |

## Dependency graph

```
storage.md ──────────────┐
                         ▼
collectors.md ──> (raw_items) ──> analysis-pipeline.md ──> (niche_candidates) ──> api.md
```

`collectors.md` writes `raw_items`; `analysis-pipeline.md` reads them and writes `niche_candidates` / `niche_analyses`; `api.md` serves the results and controls runs. All persist through `storage.md`.

## Conventions

- Every number concrete; every boundary has a violation response; no "etc."
- "must"/"must not", never "should"/"may".
- Each acceptance criterion binds a **Verify via** command and the **Evidence** that proves it. The independent verifier runs the command as written (→ `docs/verification-log.md`).
- Architectural choices cross-reference an ADR.
