"""Per-signal and per-cluster agent chains.

`run_single` runs A1 → A2 on a raw signal, short-circuiting if A1 rejects.
`run_cluster` runs A3 → A4 → A5 → A6 → (A7 if GO) → A8 on an aggregated cluster context.

Failure model:
- Each agent gets up to 2 retries on a malformed/empty/validation-failing response.
- After terminal failure, the agent's slot in PipelineResult stays None, the agent_id is
  appended to `failed_agents`, and the chain continues. Downstream user-prompt templates
  defensively substitute "unknown" via prompts._val.
- A6 partial failure is treated as NO-GO equivalent: A7 only runs if A6 explicitly returned
  verdict == "GO".

Budget:
- Optional `budget_check` callable invoked once before each LLM call. Should raise
  BudgetExceeded (or any exception) to abort. The orchestrator does not catch it — the
  caller (pipeline.run_pipeline) decides what to do.
"""

from __future__ import annotations

from typing import Any, Callable

import structlog
from pydantic import BaseModel, ValidationError

from niche_radar.agents.models import (
    A1Output,
    A2Output,
    A3Output,
    A4Output,
    A5Output,
    A6Output,
    A7Output,
    A8Output,
    PipelineResult,
)
from niche_radar.agents.prompts import PromptPack, build_system_prompt, build_user_prompt
from niche_radar.llm.base import LLMClient

logger = structlog.get_logger()

# Map agent_id to its Pydantic output model
AGENT_MODEL_CLS: dict[str, type[BaseModel]] = {
    "a1": A1Output,
    "a2": A2Output,
    "a3": A3Output,
    "a4": A4Output,
    "a5": A5Output,
    "a6": A6Output,
    "a7": A7Output,
    "a8": A8Output,
}

DEFAULT_RETRIES = 2  # refactor_prompt.md §IMPLEMENTATION REQUIREMENTS #4

# Type aliases
ClientsResolver = Callable[[str], tuple[LLMClient, float]]
BudgetCheck = Callable[[str], None]      # raises if budget exceeded
LogFn = Callable[[str], None]


class BudgetExceeded(Exception):
    """Raised by a budget_check callback when the LLM call budget for this run is spent."""


def _call_agent(
    agent_id: str,
    client: LLMClient,
    system: str,
    user: str,
    temperature: float,
    budget_check: BudgetCheck | None = None,
    retries: int = DEFAULT_RETRIES,
) -> tuple[BaseModel | None, str | None]:
    """Invoke one agent. Returns (model, None) on success, (None, error_msg) on terminal failure.

    Retries up to `retries` times on JSON parse failure or pydantic validation failure.
    Budget exceptions propagate — they're never retried.
    """
    model_cls = AGENT_MODEL_CLS[agent_id]
    last_exc: str | None = None
    # Tag client with current agent for usage tracking
    if hasattr(client, "set_agent"):
        client.set_agent(agent_id)

    for attempt in range(retries + 1):
        if budget_check is not None:
            budget_check(agent_id)  # may raise BudgetExceeded — propagates
        try:
            raw = client.complete_structured(system, user, temperature=temperature)
            if not isinstance(raw, dict):
                raise ValueError(f"non-dict response: {type(raw).__name__}")
            model = model_cls(**raw)
            # Reject empty/garbage responses. exclude_defaults catches both Nones AND
            # list fields whose default is [] (otherwise A4Output(**{}) looks non-empty
            # because of its three empty-list fields).
            if not model.model_dump(exclude_none=True, exclude_defaults=True):
                raise ValueError("response had no recognizable fields")
            return model, None
        except (ValueError, ValidationError, TypeError) as exc:
            last_exc = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "agent_call_failed",
                agent=agent_id,
                attempt=attempt + 1,
                error=last_exc,
            )
        except BudgetExceeded:
            raise
        except Exception as exc:  # network / SDK error — also worth retrying
            last_exc = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "agent_call_exception",
                agent=agent_id,
                attempt=attempt + 1,
                error=last_exc,
            )

    return None, last_exc


def _run_one(
    agent_id: str,
    ctx: dict[str, Any],
    clients: ClientsResolver,
    budget_check: BudgetCheck | None,
    log_fn: LogFn | None,
    result: PipelineResult,
    prompt_pack: PromptPack | None = None,
) -> BaseModel | None:
    """Build prompts, call the agent, attach output to result and ctx. Returns model or None."""
    client, temperature = clients(agent_id)
    system = build_system_prompt(agent_id, prompt_pack)
    user = build_user_prompt(agent_id, ctx)
    model, err = _call_agent(agent_id, client, system, user, temperature, budget_check)
    if model is None:
        result.failed_agents.append(agent_id)
        if log_fn:
            log_fn(f"{agent_id.upper()}=FAIL reason={err}")
        return None
    setattr(result, agent_id, model)
    ctx[agent_id] = model
    return model


# ---------- public entrypoints ----------


def run_single(
    raw_signal: dict[str, Any],
    clients: ClientsResolver,
    budget_check: BudgetCheck | None = None,
    log_fn: LogFn | None = None,
    prompt_pack: PromptPack | None = None,
) -> PipelineResult:
    """A1 → A2. Short-circuit if A1 rejects (is_valid_signal == False) or A1 fails."""
    result = PipelineResult(raw_signal=raw_signal)
    ctx: dict[str, Any] = {"raw_signal": raw_signal}

    a1 = _run_one("a1", ctx, clients, budget_check, log_fn, result, prompt_pack)
    if a1 is None:
        # Without A1 we can't safely proceed.
        result.short_circuited_at = "a1"
        return result

    assert isinstance(a1, A1Output)
    if a1.is_valid_signal is False:
        result.short_circuited_at = "a1"
        if log_fn:
            log_fn(f"A1=REJECT type={a1.signal_type} reason={a1.rejection_reason!r}")
        return result

    if log_fn:
        log_fn(f"A1=PASS conf={a1.confidence} type={a1.signal_type}")

    a2 = _run_one("a2", ctx, clients, budget_check, log_fn, result, prompt_pack)
    if a2 is not None and log_fn:
        log_fn("A2=DONE")
    return result


def run_cluster(
    cluster_context: dict[str, Any],
    clients: ClientsResolver,
    budget_check: BudgetCheck | None = None,
    log_fn: LogFn | None = None,
    prompt_pack: PromptPack | None = None,
) -> PipelineResult:
    """A3 → A4 → A5 → A6 → (A7 if GO) → A8.

    `cluster_context` MUST contain "raw_signal" (synthetic for the cluster, e.g. concatenated
    pain summaries) and "a2" (aggregated A2Output across the cluster's items). May optionally
    include "a1" for context.
    """
    result = PipelineResult(
        raw_signal=cluster_context.get("raw_signal", {}),
        a1=cluster_context.get("a1"),
        a2=cluster_context.get("a2"),
    )
    ctx = dict(cluster_context)  # don't mutate caller's dict

    _run_one("a3", ctx, clients, budget_check, log_fn, result, prompt_pack)
    _run_one("a4", ctx, clients, budget_check, log_fn, result, prompt_pack)
    _run_one("a5", ctx, clients, budget_check, log_fn, result, prompt_pack)
    a6 = _run_one("a6", ctx, clients, budget_check, log_fn, result, prompt_pack)

    # Per refactor_prompt.md: A7 only runs if A6 verdict == GO.
    if isinstance(a6, A6Output) and a6.verdict == "GO":
        _run_one("a7", ctx, clients, budget_check, log_fn, result, prompt_pack)

    # A8 always runs (refactor_prompt.md).
    _run_one("a8", ctx, clients, budget_check, log_fn, result, prompt_pack)

    if log_fn:
        verdict = result.a6.verdict if result.a6 else "?"
        score = result.a4.total_score if result.a4 else "?"
        feas = result.a5.feasibility_score if result.a5 else "?"
        log_fn(f"CLUSTER_DONE verdict={verdict} score={score}/70 feasibility={feas}")

    return result
