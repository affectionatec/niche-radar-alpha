# Copilot Repository Instructions

Use this file as the default behavior guide when working in this repository.

## Priority
1. Direct user instructions
2. Repository conventions in this file
3. General best practices

## Domain Language (required)
- Treat `CONTEXT.md` as the canonical glossary.
- Reuse existing domain terms from `CONTEXT.md` in code, comments, docs, and PR notes.
- If a new domain concept appears repeatedly, add it to `CONTEXT.md`.
- Avoid generic names when a domain-specific term exists.

## Engineering Workflow
For non-trivial changes:
1. Align on domain terms (`CONTEXT.md`) and existing decisions (`docs/adr/` if present).
2. Define success criteria before coding.
3. Implement the smallest complete change.
4. Run relevant tests/build checks.
5. Review for regressions and unnecessary scope.

## Coding Discipline
- Do not assume unclear requirements; surface assumptions explicitly.
- Prefer minimal, direct implementations over speculative abstractions.
- Make surgical edits only; avoid unrelated refactors.
- Every changed line should map to the requested outcome.
- Keep behavior explicit; avoid silent fallbacks and broad exception swallowing.

## Testing and Verification
- Add or update tests when behavior changes.
- Keep existing tests passing.
- For bug fixes, include a reproducible check (test or equivalent) that proves the fix.

## Documentation Discipline
- Keep `README.md`, `ARCHITECTURE.md`, `PRODUCT.md`, and `CONTEXT.md` consistent with major changes.
- Create an ADR in `docs/adr/NNNN-title.md` only when the decision is:
  1. Hard to reverse
  2. Surprising without context
  3. A real trade-off among alternatives

## Large/Iterative Work
- For long-running multi-iteration work, use the `.ralph/` workflow:
  - `.ralph/PROMPT.md`
  - `.ralph/fix_plan.md`
  - `.ralph/AGENT.md`
  - `.ralph/specs/`
