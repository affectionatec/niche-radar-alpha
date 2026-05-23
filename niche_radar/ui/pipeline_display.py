"""Rich Live visualization for the 8-agent pipeline.

Usage:
    with PipelineDisplay() as display:
        run_pipeline(db, settings, log_fn=display.log)
    # Final summary printed automatically on exit.

Pass live=False to disable Rich rendering (state still tracks for testing).
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text


class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class PhaseState:
    status: PhaseStatus = PhaseStatus.PENDING
    total: int = 0
    completed: int = 0


_ACTIVITY_MAX = 12


@dataclass
class PipelineState:
    """All mutable state for the display."""

    run_id: str = ""
    total_items: int = 0
    budget_max: int = 0
    budget_used: int = 0
    start_time: float = field(default_factory=time.time)

    phase_a: PhaseState = field(default_factory=PhaseState)
    phase_b: PhaseState = field(default_factory=PhaseState)
    phase_c: PhaseState = field(default_factory=PhaseState)
    phase_d: PhaseState = field(default_factory=PhaseState)

    a1_passed: int = 0
    a1_rejected: int = 0
    a2_done: int = 0

    verdicts: dict[str, int] = field(default_factory=dict)
    niches_persisted: list[str] = field(default_factory=list)

    finished: bool = False
    aborted: bool = False

    activity: list[str] = field(default_factory=list)


# ---------- regex patterns ----------

_RE_PIPELINE_INIT = re.compile(
    r"pipeline_run=(\S+)\s+items=(\d+)\s+budget=(\d+)"
)
_RE_PHASE_START = re.compile(r"phase=([ABCD])\s+(\w+)=(\d+)")
_RE_PHASE_A_DONE = re.compile(r"phase=A\s+done\s+passed=(\d+)\s+rejected=(\d+)")
_RE_PHASE_ITEM = re.compile(r"phase_a_item=(\d+)/(\d+)")
_RE_PHASE_C_CLUSTER = re.compile(r"phase_c_cluster=(\d+)/(\d+)")
_RE_PHASE_B_SKIP = re.compile(r"phase=B\s+skip")
_RE_PHASE_C_DONE = re.compile(r"phase=C\s+done")
_RE_PHASE_D_START = re.compile(r"phase=D\s+persisting\s+(\d+)\s+clusters?")
_RE_PHASE_D_DRY = re.compile(r"phase=D\s+dry_run")
_RE_A1_PASS = re.compile(r"A1=PASS")
_RE_A1_REJECT = re.compile(r"A1=REJECT")
_RE_A1_FAIL = re.compile(r"A1=FAIL")
_RE_A2_DONE = re.compile(r"A2=DONE")
_RE_AGENT_CALL = re.compile(r"A[1-8]=(PASS|REJECT|DONE|FAIL)")
_RE_CLUSTER_DONE = re.compile(r"CLUSTER_DONE\s+verdict=(\S+)\s+score=(\S+)")
_RE_CLUSTER_PERSIST = re.compile(r"cluster=\S+\s+verdict=\S+.*?niche=(\S+)")
_RE_PIPELINE_DONE = re.compile(r"pipeline_done")
_RE_PIPELINE_ABORTED = re.compile(r"pipeline_aborted")
_RE_PIPELINE_SKIPPED = re.compile(r"pipeline_skipped")

_AGENT_NAMES = {
    "A1": "Signal Filter",
    "A2": "Pain Extractor",
    "A3": "Market Researcher",
    "A4": "Opportunity Scorer",
    "A5": "Feasibility Analyst",
    "A6": "Decision Gate",
    "A7": "Product Designer",
    "A8": "Summary & Brief",
}


class PipelineDisplay:
    """Rich Live display for the 8-agent pipeline.

    Args:
        console: Rich Console instance (default: new Console).
        live: If False, skip Rich Live rendering (useful for tests and --no-tui).
    """

    def __init__(
        self,
        console: Console | None = None,
        live: bool = True,
    ) -> None:
        self._console = console or Console()
        self._live_enabled = live
        self._live: Live | None = None
        self._lock = threading.Lock()
        self.state = PipelineState()

    def __enter__(self) -> "PipelineDisplay":
        if self._live_enabled:
            self._live = Live(
                self._build_layout(),
                console=self._console,
                refresh_per_second=4,
                transient=True,
            )
            self._live.__enter__()
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._live is not None:
            self._live.__exit__(*exc)
            self._live = None
        if self._live_enabled:
            self._print_summary()

    def log(self, message: str) -> None:
        """Drop-in replacement for print() as log_fn. Thread-safe."""
        with self._lock:
            self._parse(message)
            self._add_activity(message)
        if self._live is not None:
            self._live.update(self._build_layout())

    # ---------- parsing ----------

    def _parse(self, msg: str) -> None:  # noqa: C901 — intentionally flat switch
        s = self.state

        m = _RE_PIPELINE_INIT.search(msg)
        if m:
            s.run_id = m.group(1)
            s.total_items = int(m.group(2))
            s.budget_max = int(m.group(3))
            return

        if _RE_PIPELINE_DONE.search(msg):
            s.finished = True
            for p in (s.phase_a, s.phase_b, s.phase_c, s.phase_d):
                if p.status == PhaseStatus.RUNNING:
                    p.status = PhaseStatus.DONE
            return

        if _RE_PIPELINE_ABORTED.search(msg):
            s.aborted = True
            return

        if _RE_PIPELINE_SKIPPED.search(msg):
            s.finished = True
            return

        m = _RE_PHASE_A_DONE.search(msg)
        if m:
            s.phase_a.status = PhaseStatus.DONE
            s.a1_passed = int(m.group(1))
            s.a1_rejected = int(m.group(2))
            s.phase_a.completed = s.a1_passed + s.a1_rejected
            return

        m = _RE_PHASE_ITEM.search(msg)
        if m:
            s.phase_a.completed = int(m.group(1))
            return

        m = _RE_PHASE_C_CLUSTER.search(msg)
        if m:
            s.phase_c.completed = int(m.group(1))
            return

        if _RE_PHASE_B_SKIP.search(msg):
            s.phase_b.status = PhaseStatus.DONE
            return

        if _RE_PHASE_C_DONE.search(msg):
            s.phase_c.status = PhaseStatus.DONE
            return

        m = _RE_PHASE_D_START.search(msg)
        if m:
            s.phase_d.status = PhaseStatus.RUNNING
            s.phase_d.total = int(m.group(1))
            return

        if _RE_PHASE_D_DRY.search(msg):
            s.phase_d.status = PhaseStatus.DONE
            return

        m = _RE_PHASE_START.search(msg)
        if m:
            phase_letter = m.group(1)
            count = int(m.group(3))
            phase = {
                "A": s.phase_a, "B": s.phase_b,
                "C": s.phase_c, "D": s.phase_d,
            }.get(phase_letter)
            if phase:
                phase.status = PhaseStatus.RUNNING
                phase.total = count
            return

        if _RE_A1_PASS.search(msg):
            s.a1_passed += 1
            s.budget_used += 1
            return
        if _RE_A1_REJECT.search(msg):
            s.a1_rejected += 1
            s.budget_used += 1
            return
        if _RE_A1_FAIL.search(msg):
            s.budget_used += 1
            return
        if _RE_A2_DONE.search(msg):
            s.a2_done += 1
            s.budget_used += 1
            return

        m = _RE_CLUSTER_DONE.search(msg)
        if m:
            s.phase_c.completed += 1
            verdict = m.group(1)
            s.verdicts[verdict] = s.verdicts.get(verdict, 0) + 1
            return

        m = _RE_CLUSTER_PERSIST.search(msg)
        if m:
            s.phase_d.completed += 1
            s.niches_persisted.append(m.group(1))
            return

        m = _RE_AGENT_CALL.search(msg)
        if m:
            s.budget_used += 1

    def _add_activity(self, msg: str) -> None:
        keywords = ("A1=", "A2=", "A3=", "A4=", "A5=", "A6=", "A7=", "A8=",
                     "CLUSTER_DONE", "phase=", "pipeline_")
        if any(k in msg for k in keywords):
            ts = time.strftime("%H:%M:%S")
            self.state.activity.append(f"  {ts}  {msg}")
            if len(self.state.activity) > _ACTIVITY_MAX:
                self.state.activity = self.state.activity[-_ACTIVITY_MAX:]

    # ---------- rendering ----------

    def _build_layout(self) -> Group:
        s = self.state
        elapsed = time.time() - s.start_time
        elapsed_str = _fmt_duration(elapsed)

        # Header
        parts = []
        if s.run_id:
            parts.append(f"Run: [bold]{s.run_id[:8]}[/bold]")
        if s.budget_max:
            parts.append(f"Budget: [cyan]{s.budget_used}[/cyan]/{s.budget_max} LLM calls")
        parts.append(f"Elapsed: [yellow]{elapsed_str}[/yellow]")
        header = "  │  ".join(parts)

        # Build markup string for the stages panel
        lines: list[str] = []
        lines.append("")
        lines.append(f"  {header}")
        lines.append("")

        _render_phase_lines(
            lines, "A", "Signal Validation", s.phase_a,
            subs=[
                ("A1", "Signal Filter", _detail_a1(s)),
                ("A2", "Pain Extractor", _detail_a2(s)),
            ],
        )

        b_detail = f"{s.phase_b.total} extractions" if s.phase_b.status == PhaseStatus.DONE and s.phase_b.total else ""
        _render_phase_lines(lines, "B", "Clustering", s.phase_b, detail=b_detail)

        _render_phase_lines(
            lines, "C", "Deep Analysis", s.phase_c,
            subs=[
                ("A3", "Market Researcher", ""),
                ("A4", "Opportunity Scorer", ""),
                ("A5", "Feasibility Analyst", ""),
                ("A6", "Decision Gate", ""),
                ("A7", "Product Designer", ""),
                ("A8", "Summary & Brief", ""),
            ],
            detail=_verdicts_str(s.verdicts) if s.verdicts else "",
        )

        d_detail = ", ".join(s.niches_persisted[-3:]) if s.niches_persisted else ""
        _render_phase_lines(lines, "D", "Persistence", s.phase_d, detail=d_detail)

        lines.append("")
        markup = "\n".join(lines)
        stage_panel = Panel(
            Text.from_markup(markup),
            title="[bold]Niche Radar Pipeline[/bold]",
            border_style="blue",
        )

        if s.activity:
            activity_text = "\n".join(s.activity)
        else:
            activity_text = "  [dim]Waiting for pipeline to start...[/dim]"
        activity_panel = Panel(
            Text.from_markup(activity_text),
            title="Activity",
            border_style="dim",
            height=min(len(s.activity) + 2, _ACTIVITY_MAX + 2) if s.activity else 3,
        )

        return Group(stage_panel, activity_panel)

    def _print_summary(self) -> None:
        s = self.state
        elapsed = _fmt_duration(time.time() - s.start_time)
        c = self._console

        if s.aborted:
            c.print(f"\n[bold red]✗ Pipeline aborted[/bold red] after {elapsed}\n")
        elif s.finished:
            c.print(f"\n[bold green]✓ Pipeline complete[/bold green] in {elapsed}\n")
        else:
            c.print(f"\n[yellow]Pipeline ended[/yellow] after {elapsed}\n")

        if s.total_items:
            c.print(f"  Phase A  Signal Validation    {s.total_items} items → {s.a1_passed} passed ({_pct(s.a1_passed, s.total_items)})")
        if s.phase_b.total:
            c.print(f"  Phase B  Clustering           {s.phase_b.total} extractions → {s.phase_c.total or '?'} clusters")
        if s.phase_c.total:
            v = s.verdicts
            vparts = [f"{v.get(k, 0)} {k}" for k in ("GO", "NO-GO", "PIVOT") if v.get(k)]
            c.print(f"  Phase C  Deep Analysis        {s.phase_c.total} clusters → {', '.join(vparts) or 'n/a'}")
        if s.phase_d.total:
            c.print(f"  Phase D  Persistence          {len(s.niches_persisted)} niches persisted")

        if s.budget_max:
            c.print(f"\n  Budget: {s.budget_used}/{s.budget_max} LLM calls ({_pct(s.budget_used, s.budget_max)})")
        c.print()


# ---------- helpers ----------


def _status_icon(status: PhaseStatus) -> str:
    return {
        PhaseStatus.PENDING: "○",
        PhaseStatus.RUNNING: "[cyan]●[/cyan]",
        PhaseStatus.DONE: "[green]✓[/green]",
        PhaseStatus.FAILED: "[red]✗[/red]",
    }[status]


def _render_phase_lines(
    lines: list[str],
    letter: str,
    name: str,
    phase: PhaseState,
    subs: list[tuple[str, str, str]] | None = None,
    detail: str = "",
) -> None:
    icon = _status_icon(phase.status)
    progress = ""
    if phase.status == PhaseStatus.RUNNING and phase.total > 0:
        bar_width = 20
        filled = int(bar_width * phase.completed / phase.total) if phase.total else 0
        bar = "█" * filled + "░" * (bar_width - filled)
        progress = f"  {bar}  {phase.completed}/{phase.total}  {_pct(phase.completed, phase.total)}"
    elif phase.status == PhaseStatus.DONE and detail:
        progress = f"  {detail}"
    elif phase.status == PhaseStatus.PENDING:
        progress = "  [dim]⏳ Waiting[/dim]"

    bold_open = "[bold]" if phase.status == PhaseStatus.RUNNING else ""
    bold_close = "[/bold]" if phase.status == PhaseStatus.RUNNING else ""
    lines.append(f"  {icon} {bold_open}Phase {letter}  {name:<22s}{progress}{bold_close}")

    if subs and phase.status != PhaseStatus.PENDING:
        for i, (agent_id, agent_name, agent_detail) in enumerate(subs):
            connector = "└─" if i == len(subs) - 1 else "├─"
            line = f"    [dim]{connector} {agent_id} {agent_name}"
            if agent_detail:
                line += f"  {agent_detail}"
            line += "[/dim]"
            lines.append(line)

    lines.append("")


def _detail_a1(s: PipelineState) -> str:
    if s.a1_passed or s.a1_rejected:
        return f"✓ {s.a1_passed} passed · {s.a1_rejected} rejected"
    return ""


def _detail_a2(s: PipelineState) -> str:
    if s.a2_done:
        return f"✓ {s.a2_done} extracted"
    return ""


def _verdicts_str(verdicts: dict[str, int]) -> str:
    parts = [f"{v} {k}" for k, v in verdicts.items() if v]
    return ", ".join(parts)


def _pct(n: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{100 * n // total}%"


def _fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"
