#!/usr/bin/env python3
"""Live-collector canary -- detects scraper rot the mocked test suite cannot see.

Usage:
  python -m niche_radar.eval.canary [--sources hn,github,...] [--strict]

Runs the keyless collectors against the REAL web (no credentials required,
in-memory DB, nothing persisted) and reports per-source item yield. The
481-test suite mocks every network call, so a platform changing its HTML or
API silently zeroes a source without failing any test — this canary is the
tripwire.

Exit code:
  0  healthy (strict: every source yielded items; default: at least half did)
  1  rot detected

Intended to run on a weekly schedule (.github/workflows/canary.yml), never as
a PR gate — live endpoints are allowed to flake without blocking merges.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

# Sources that need no credentials and are expected to yield items on any run.
DEFAULT_CANARY_SOURCES = [
    "hn",
    "github",
    "stack_overflow",
    "product_hunt",
    "indie_hackers",
    "v2ex",
    "xueqiu",
    "bilibili",
    "app_store",
    "play_store",
]


@dataclass
class CanaryResult:
    source: str
    status: str  # collector status, or "exception"
    items: int
    error: str | None = None


def evaluate_canary(results: list[CanaryResult], strict: bool = False) -> tuple[bool, list[str]]:
    """Pure verdict logic — separated from network I/O so it is unit-testable.

    Returns (healthy, report_lines).
    """
    lines: list[str] = []
    zero_sources = [r for r in results if r.items == 0]
    for r in results:
        mark = "OK  " if r.items > 0 else "ROT?"
        line = f"[{mark}] {r.source:15s} status={r.status:10s} items={r.items}"
        if r.error:
            line += f" error={r.error[:120]}"
        lines.append(line)

    if not results:
        return False, ["no canary results — nothing ran"]

    if strict:
        healthy = not zero_sources
    else:
        healthy = len(zero_sources) <= len(results) / 2

    verdict = "HEALTHY" if healthy else "ROT DETECTED"
    lines.append(
        f"\nCanary verdict: {verdict} — "
        f"{len(results) - len(zero_sources)}/{len(results)} sources yielded items"
        f"{' (strict mode)' if strict else ''}"
    )
    return healthy, lines


def run_canary(sources: list[str]) -> list[CanaryResult]:
    """Run each collector live against an in-memory DB. Nothing is persisted."""
    from niche_radar.collectors import _get_collector
    from niche_radar.config import Settings
    from niche_radar.storage.database import get_db

    settings = Settings(database_url="sqlite:///:memory:")
    db = get_db(settings.database_url)

    results: list[CanaryResult] = []
    for source in sources:
        try:
            collector = _get_collector(source)
            if not type(collector).is_available(db, settings):
                results.append(CanaryResult(source, "unavailable", 0, "credential-gated"))
                continue
            r = collector.collect(settings=settings, dry_run=False, db=db)
            results.append(
                CanaryResult(source, r.status, r.items_collected, r.error_message)
            )
        except Exception as exc:  # a crash is itself a canary signal, keep going
            results.append(CanaryResult(source, "exception", 0, f"{type(exc).__name__}: {exc}"))
    return results


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    sources = list(DEFAULT_CANARY_SOURCES)
    strict = False

    i = 0
    while i < len(args):
        if args[i] == "--sources" and i + 1 < len(args):
            sources = [s.strip() for s in args[i + 1].split(",") if s.strip()]
            i += 2
        elif args[i] == "--strict":
            strict = True
            i += 1
        else:
            i += 1

    print(f"Canary sources: {', '.join(sources)}")
    results = run_canary(sources)
    healthy, lines = evaluate_canary(results, strict=strict)
    print("\n".join(lines))
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
