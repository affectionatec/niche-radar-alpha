# CLAUDE.md — Unified Agent Configuration

## Priority Order (conflicts resolved top-down)
1. Explicit instructions in this file / user's direct requests
2. Superpowers skills (using-superpowers)
3. Karpathy coding discipline
4. Matt Pocock domain discipline
5. Ralph loop defaults

---

## 1. Load Skills at Session Start

Before any task, activate in this order:

```
/using-superpowers          ← Superpowers workflow dispatcher
/karpathy-guidelines        ← Coding discipline overlay
/ralph                      ← Autonomous loop methodology
/setup-matt-pocock-skills   ← Scaffolds CONTEXT.md, ADR layout, issue tracker
```

Run `/setup-matt-pocock-skills` once per repo — it configures the issue tracker,
triage labels, and doc layout used by `/to-issues`, `/triage`, and `/grill-with-docs`.

---

## 2. Matt Pocock — Domain Discipline (always active)

Matt Pocock's skills fix the root cause of most agent failures: misalignment and
a lack of shared language. Apply before writing any code.

### Shared Language: CONTEXT.md

Every repo should have a `CONTEXT.md` at the root — a glossary of domain terms.
- Use terms from CONTEXT.md in all code, comments, and variable names
- When a new concept emerges during a session, add it to CONTEXT.md immediately
- Never use generic labels ("Service", "Handler", "Manager") when a domain term exists

### When to use each skill

| Situation | Skill |
|---|---|
| Starting any non-trivial feature | `/grill-with-docs` — aligns plan against CONTEXT.md + ADRs |
| Non-code planning / brainstorming | `/grill-me` — exhaustive interview before committing |
| Unfamiliar area of the codebase | `/zoom-out` — maps modules using domain vocabulary |
| Architecture feels tangled | `/improve-codebase-architecture` — finds deep vs shallow modules |
| Writing features with tests | `/tdd` — red-green-refactor, one vertical slice at a time |
| Hard bug or regression | `/diagnose` — reproduce → minimise → hypothesise → fix → regression-test |
| Conversation to PRD | `/to-prd` — synthesises current context into a GitHub issue |
| PRD to tasks | `/to-issues` — breaks PRD into independently-grabbable vertical slices |
| Context window filling up | `/handoff` — compacts session for next agent to continue |
| Token-heavy session | `/caveman` — ~75% token reduction, no loss of technical accuracy |

### ADR discipline

Create an ADR (`docs/adr/NNNN-title.md`) only when ALL THREE are true:
1. Hard to reverse
2. Surprising without context — a future reader would ask "why?"
3. Result of a real trade-off — genuine alternatives existed

Skip ephemeral or self-evident reasons. One ADR for the right decision beats
five ADRs for obvious ones.

---

## 3. Superpowers Workflow (7-stage gate)

Every non-trivial feature must pass through:

```
grill-with-docs → brainstorm → spec → write-plan → execute-plan → test → review → ship
```

**grill-with-docs runs before brainstorm**, not after. It surfaces misalignment
and sharpens terminology before any plan is formed.

**Never skip stages.** If Claude jumps straight to code, type `/using-superpowers` to reset.

Useful commands:
- `/grill-with-docs`         — Pre-flight: align plan against CONTEXT.md and ADRs
- `/superpowers:brainstorm`  — Start here after grilling
- `/superpowers:write-plan`  — After design sign-off
- `/superpowers:execute-plan`— Batched execution with checkpoints
- `/superpowers:debug`       — 4-phase root cause debugging (or use `/diagnose`)
- `/superpowers:code-review` — Pre-merge review

---

## 4. Karpathy Coding Discipline (always active)

Apply to every code edit, inside every Superpowers stage:

**Don't assume.**
State assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them — don't pick silently.

**Minimum viable code.**
No speculative features. No abstractions for single-use code.
If you wrote 200 lines and it could be 50, rewrite it.

**Surgical edits only.**
Touch only what the task requires.
Don't "improve" adjacent code, comments, or formatting unprompted.

**Goal-driven, not step-driven.**
Define success criteria, then iterate to meet them.
Don't ask for permission at every micro-step.

---

## 5. Ralph — Autonomous Loop for Long Tasks

Use Ralph when a task requires many iterations or spans context windows.
Run `/handoff` before starting Ralph if the current session is already long.

```
/ralph-loop   ← Start autonomous iteration (reads .ralph/PROMPT.md)
/cancel-ralph ← Interrupt the loop
```

**Ralph folder structure:**
```
.ralph/
├── PROMPT.md      ← Main task instructions for the loop
├── fix_plan.md    ← Prioritised task list (Ralph works from top)
├── AGENT.md       ← Build/run commands
└── specs/         ← Requirements / acceptance criteria
```

**When to use Ralph:**
- Task exceeds a single context window
- Repetitive multi-file refactors
- "Keep going until all tests pass" type tasks

---

## 6. Sub-Agent Orchestration

Decompose parallel-safe work across sub-agents:

**Spawn sub-agents for:**
- Independent file scopes (no shared state conflicts)
- Research vs. implementation split
- Test generation (separate from feature code)
- Security / code review pass

**Rules:**
- Each sub-agent gets a clearly bounded file scope
- Sub-agents report back to orchestrator before merging
- Use Ralph loop within a sub-agent for iterative tasks

**Example decomposition:**
```
Task: "Implement feature X with full test coverage"
├── Sub-agent A: /tdd — write failing tests (tests/ only)
├── Sub-agent B: implement feature (src/ only)
├── Sub-agent C: /diagnose — security + regression review (read-only)
└── Orchestrator: integrate, run all tests, ship
```

---

## 7. Session Reset Checklist

If Claude seems to be drifting or skipping steps:
1. `/using-superpowers` — re-activate Superpowers dispatcher
2. `/zoom-out` — re-orient in the codebase using domain vocabulary
3. `/handoff` — compact context if the session is getting long
4. `/cancel-ralph` + check `.ralph/fix_plan.md` — if stuck in a loop
5. Remind: "Apply Karpathy discipline. Check CONTEXT.md for correct terms."