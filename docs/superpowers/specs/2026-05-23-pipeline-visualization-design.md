# Pipeline Visualization — Design Spec

**Date:** 2026-05-23
**Status:** Draft

## Problem

Running `python -m niche_radar analyze` outputs flat structured log lines via `log_fn=print`:
```
phase=A items=245
A1=PASS conf=0.95 type=pain_point
A1=REJECT type=noise reason='...'
phase=A done passed=182 rejected=63
phase=B extractions=182
phase=C clusters=45
CLUSTER_DONE verdict=GO score=62/70 feasibility=0.85
phase=D persisting 12 clusters
pipeline_done {...}
```

No progress indication, no stage structure, no agent activity visibility. Users can't tell which phase is running, how far along it is, or what agents are doing.

## Goal

Replace the scrolling log output with a GitHub Actions-style pipeline visualization using Rich Live display. Show pipeline stages, progress, active agents, and a scrolling activity log — all in one terminal view.

## Architecture

### New module: `niche_radar/ui/pipeline_display.py`

A single new module containing the `PipelineDisplay` class. No changes to the pipeline engine itself — the display hooks into the existing `log_fn` callback.

### Design principle: observer, not controller

`PipelineDisplay` is a **read-only observer**. It parses `log_fn` messages to update its state. The pipeline code (`pipeline.py`, `orchestrator.py`) remains untouched except for one change: `run_pipeline` emits a few additional structured log messages to provide richer data for the display.

### Integration point

In `__main__.py:cmd_analyze`, replace `log_fn=print` with `log_fn=display.log` where `display` is a `PipelineDisplay` instance managed via context manager.

## Terminal Layout

```
╭─ Niche Radar Pipeline ─────────────────────────────────────────────────╮
│                                                                        │
│  Run: a1b2c3d4  │  Budget: 45/310 LLM calls  │  Elapsed: 2m 34s      │
│                                                                        │
│  ● Phase A  Signal Validation     ████████████████░░░░  182/245  74%  │
│    ├─ A1 Signal Filter            ✓ 182 passed · 63 rejected          │
│    └─ A2 Pain Extractor           ⏳ 3 running                        │
│                                                                        │
│  ○ Phase B  Clustering            ⏳ Waiting                          │
│                                                                        │
│  ○ Phase C  Deep Analysis         ⏳ Waiting                          │
│    ├─ A3 Market Researcher                                             │
│    ├─ A4 Opportunity Scorer                                            │
│    ├─ A5 Feasibility Analyst                                           │
│    ├─ A6 Decision Gate                                                 │
│    ├─ A7 Product Designer                                              │
│    └─ A8 Summary                                                       │
│                                                                        │
│  ○ Phase D  Persistence           ⏳ Waiting                          │
│                                                                        │
╰────────────────────────────────────────────────────────────────────────╯
╭─ Activity ──────────────────────────────────────────────────────────────╮
│  17:32:15  A1  ✓ PASS   conf=0.95 type=pain_point                     │
│  17:32:15  A1  ✗ REJECT type=noise reason="not actionable"            │
│  17:32:16  A2  ✓ DONE   pain="No affordable tool for..."              │
│  17:32:17  A1  ✓ PASS   conf=0.88 type=frustration                    │
│  17:32:18  A1  ✗ REJECT type=spam                                     │
╰────────────────────────────────────────────────────────────────────────╯
```

### Layout components

1. **Header bar** — pipeline run ID (truncated), budget gauge, elapsed timer
2. **Stage panel** — 4 phases with status icons, progress bars, agent sub-items
3. **Activity log** — scrolling log of recent agent actions (last 12 lines)

### Status icons

| Icon | Meaning |
|------|---------|
| `○`  | Pending (not started) |
| `●`  | Running (animated spinner via Rich) |
| `✓`  | Completed successfully |
| `✗`  | Failed / aborted |

### Phase-specific details

**Phase A:** Progress bar (items processed / total). Sub-agents A1 and A2 show pass/reject counts and active worker count.

**Phase B:** No progress bar (clustering is a single operation). Shows extraction count and cluster count when done.

**Phase C:** Progress bar (clusters processed / total). Shows each agent (A3-A8) with completed count. Shows current verdicts as clusters finish.

**Phase D:** Progress bar (clusters persisted / total). Shows niche keywords as they're written.

## State Machine

Each phase transitions through: `pending → running → done | failed`

```
PipelineState:
  phase_a: PhaseState (pending|running|done|failed)
  phase_b: PhaseState
  phase_c: PhaseState
  phase_d: PhaseState
  
PhaseState:
  status: pending | running | done | failed
  total: int
  completed: int
  details: dict  # phase-specific counters
```

## Log Message Parsing

The display parses existing `log_fn` messages via prefix matching:

| Pattern | State update |
|---------|-------------|
| `pipeline_run=<id> items=<n> budget=<n>` | Init header, set phase_a.total |
| `phase=A items=<n>` | Phase A → running |
| `A1=PASS ...` | Increment A1 pass counter |
| `A1=REJECT ...` | Increment A1 reject counter |
| `A2=DONE` | Increment A2 done counter |
| `phase=A done passed=<n> rejected=<n>` | Phase A → done |
| `phase=B extractions=<n>` | Phase B → running |
| `phase=B skip empty` | Phase B → done (0 clusters) |
| `phase=C clusters=<n>` | Phase C → running, set total |
| `CLUSTER_DONE verdict=<v> score=<s>` | Increment phase C completed |
| `phase=C done` | Phase C → done |
| `phase=D persisting <n> clusters` | Phase D → running |
| `cluster=<id> verdict=<v> ... niche=<kw>` | Increment phase D completed |
| `pipeline_done ...` | All phases → done |
| `pipeline_aborted ...` | Current phase → failed |

### New log messages from pipeline.py

To provide richer progress data, add these `log_fn` calls to `pipeline.py`:

1. **Per-item completion in Phase A**: After each `_phase_a_for_item` future completes, emit `phase_a_item_done` so the progress bar advances per-item (not just at phase end). Current code processes futures in a loop — add a counter.

2. **Cluster count after Phase B**: Already emitted implicitly. No change needed.

3. **Per-cluster completion in Phase C**: After each `_phase_c_for_cluster` future completes, emit `phase_c_cluster_done`. Current code processes futures but doesn't log per-cluster.

4. **Per-cluster persistence in Phase D**: Already emitted via `cluster=<id> ...` messages. No change needed.

## New files

| File | Purpose |
|------|---------|
| `niche_radar/ui/__init__.py` | Package marker |
| `niche_radar/ui/pipeline_display.py` | `PipelineDisplay` class |
| `tests/test_ui/test_pipeline_display.py` | Unit tests for state parsing |

## Changes to existing files

| File | Change |
|------|--------|
| `niche_radar/__main__.py` | Import display, wrap `cmd_analyze` with `PipelineDisplay` context manager, add `--no-tui` flag |
| `niche_radar/agents/pipeline.py` | Add ~4 per-item/per-cluster progress log messages |
| `pyproject.toml` | Add `rich>=13.0` to dependencies |
| `requirements.txt` | Add `rich>=13.0,<14.0` |

## CLI interface

```bash
# Default: TUI visualization (when stdout is a TTY)
python -m niche_radar analyze

# Force plain text (for CI, logging, piping)
python -m niche_radar analyze --no-tui

# Auto-detect: if stdout is not a TTY, fall back to plain text
```

## PipelineDisplay API

```python
class PipelineDisplay:
    """Rich Live display for the 8-agent pipeline."""
    
    def __init__(self, console: Console | None = None):
        ...
    
    def __enter__(self) -> "PipelineDisplay":
        """Start the Rich Live display."""
        ...
    
    def __exit__(self, *exc) -> None:
        """Stop the live display, print final summary."""
        ...
    
    def log(self, message: str) -> None:
        """Drop-in replacement for print() as log_fn.
        Parses the message, updates state, refreshes display."""
        ...
    
    def _build_layout(self) -> Table:
        """Render current state as a Rich renderable."""
        ...
```

## Final summary display

When the pipeline finishes, the live display stops and prints a static summary:

```
✓ Pipeline complete in 4m 12s

  Phase A  Signal Validation    245 items → 182 passed (74%)
  Phase B  Clustering           182 extractions → 45 clusters
  Phase C  Deep Analysis        45 clusters → 12 GO, 28 NO-GO, 5 failed
  Phase D  Persistence          12 niches persisted

  Budget: 287/310 LLM calls (92%)
  Agents: A1=245 A2=182 A3=45 A4=45 A5=45 A6=45 A7=12 A8=45
```

## Thread safety

Phase A and C run agents in parallel via `ThreadPoolExecutor(max_workers=8)`. The `log_fn` callback is invoked from worker threads. `PipelineDisplay.log()` must be thread-safe.

**Solution:** Use a `threading.Lock` around state mutations in `log()`. Rich's `Live` object handles concurrent `update()` calls safely.

## Testing strategy

1. **Unit tests for log parsing:** Feed known log messages into `PipelineDisplay.log()`, assert state transitions.
2. **Rendering test:** Verify `_build_layout()` produces a Rich renderable without errors for various states (empty, mid-run, complete, failed).
3. **Integration test:** Mock pipeline that emits realistic log sequence, verify display doesn't crash.
4. **No live terminal tests** — Rich rendering is visual; we test state logic only.

## Success criteria

1. `python -m niche_radar analyze` shows the pipeline visualization by default
2. All 4 phases display with correct status progression
3. Progress bars advance in real-time during Phase A and C
4. Agent activity log scrolls with recent events
5. `--no-tui` flag produces plain text output (existing behavior)
6. Auto-detect: non-TTY stdout falls back to plain text
7. Thread-safe: no crashes with 8 parallel workers
8. All existing tests pass unchanged
9. New tests cover state parsing and rendering
