---
name: generate-project-docs
description: >
  Scan the entire codebase and generate lean, accurate documentation:
  CONTEXT.md (domain glossary), ARCHITECTURE.md (system design with Mermaid),
  PRODUCT.md (problem, users, features), and README.md (quick start).
  Trigger when user asks to "document the project", "generate docs",
  "write architecture docs", or "build a shared language for this repo".
  Produces only essential information — no padding, no boilerplate,
  no placeholder names in diagrams.
user-invocable: true
allowed-tools: [Read, Glob, Grep, Bash, Write]
argument-hint: "[--files CONTEXT|ARCHITECTURE|PRODUCT|README] [--update] [--dry-run]"
---

# Generate Project Documentation

Four lean, accurate files from live codebase analysis.
Every line earns its place. No hallucination. No placeholders.

## Flags

| Flag | Effect |
|------|--------|
| `--files CONTEXT` | Generate CONTEXT.md only |
| `--files ARCHITECTURE` | Generate ARCHITECTURE.md only |
| `--files PRODUCT` | Generate PRODUCT.md only |
| `--files README` | Generate README.md only |
| `--update` | Patch existing files; preserve `<!-- manual -->` sections |
| `--dry-run` | Print to terminal, write nothing |

Default: generate all four files.

---

## Phase 0 — Domain Discovery (always first)

Before reading any source code, check what already exists:

```
1. cat CONTEXT.md              (existing domain glossary — do NOT overwrite terms)
2. ls docs/adr/ 2>/dev/null    (existing architectural decisions — do NOT re-litigate)
3. cat CONTEXT-MAP.md          (multi-context repos — map of where each context lives)
```

If CONTEXT.md exists: use its vocabulary exactly in every diagram node, every
component name, every prose description. Contradicting the glossary is a bug.

If docs/adr/ exists: read every ADR before writing Key Decisions in ARCHITECTURE.md.
Do not surface a decision that an ADR already resolves.

---

## Phase 1 — Codebase Scan

Run in order. Stop when you can answer the four questions below.

```
1. find . -type f | grep -v node_modules | grep -v .git | head -300
2. cat package.json OR pyproject.toml OR go.mod OR Cargo.toml OR pom.xml
3. head -80 of entry points: main.*, index.*, app.*, cmd/*, server.*
4. ls -1 src/ OR lib/ OR app/ OR internal/ OR packages/     (one level only)
5. Spot-read 4–6 core source files to extract domain concepts and module shape
6. cat .env.example OR docker-compose.yml OR k8s/*.yaml     (infra signals)
7. grep -r "TODO\|FIXME\|HACK\|XXX" --include="*.ts,*.py,*.go" | head -20
   (reveals known pain points worth noting in Key Decisions)
```

**Stop when you can answer:**
- What does this system do, and what domain does it operate in?
- What are the deep modules — high behaviour behind a small interface?
- What terms does the codebase already use for its core concepts?
- What does a developer need to run this locally?

**Deletion test (Matt Pocock):** For each module you consider documenting,
ask: "If I deleted this, would complexity concentrate here, or scatter across
N callers?" Concentrate = deep module, worth documenting. Scatter = shallow
pass-through, skip it or fold into parent.

---

## Phase 2 — Build Domain Glossary

Extract canonical terms before writing any doc.

Rules:
- Use the term the code already uses (variable names, file names, comments)
- If the code uses 3 synonyms for one concept, pick the most precise one
- Do NOT use generic labels: "Service", "Handler", "Manager", "Helper"
- Each term: one sentence definition, the file or module where it lives

This glossary becomes CONTEXT.md and the vocabulary for every diagram.

---

## Phase 3 — Diagram Selection

Choose based on what the codebase actually contains.
Never generate a diagram you cannot populate with real names from Phase 2.

| System shape | Primary diagram | Secondary |
|---|---|---|
| Microservices / API gateway | C4 Container (`flowchart TD`) | Sequence per key flow |
| Monolith with layers | Layered arch (`flowchart TD`) | Sequence for main user flow |
| CLI / script | Execution flowchart | None needed |
| Event-driven / queue | Sequence with queue nodes | State diagram |
| Data pipeline | `flowchart LR` | ER diagram |
| Frontend + backend | C4 Context + Container | Sequence for auth / data fetch |

**Mermaid rules:**
- Node labels = CONTEXT.md terms only. Never "ServiceA", "Database1", "Module2".
- Max 12 nodes per diagram. Split into two named diagrams if larger.
- Sequence diagrams: use real function/endpoint names where known.
- Always fenced: ` ```mermaid `.
- Max 3 Mermaid diagrams total across ARCHITECTURE.md.
- Validate mentally before writing: would this render without syntax errors?

---

## Phase 4 — Write Files

Confirm before writing unless `--dry-run` is set. Then write all at once.

---

### CONTEXT.md  ← write this first, others depend on it

```markdown
# Domain Glossary

> Canonical terms for this codebase. Use these exact words in code,
> comments, and conversation. Last updated: YYYY-MM-DD.

## [Term]
**Definition**: [One sentence. What it is, not what it does.]
**Lives in**: `path/to/module`
**Distinct from**: [nearest confusable term, if any]

## [Term]
...
```

Rules:
- 5–15 terms. Only concepts that appear in multiple places in the code.
- Skip infrastructure terms (Redis, Postgres) unless the project wraps them with domain meaning.
- If CONTEXT.md already exists, append new terms only. Never rewrite existing ones.
- Add `<!-- manual -->` to any term the user has hand-written.

---

### ARCHITECTURE.md

```markdown
# Architecture

## Overview

[2–3 sentences: system purpose, scale, key design constraint.]

[HIGH-LEVEL DIAGRAM — C4 Context or top-level flowchart using CONTEXT.md terms]

## Modules

[One entry per deep module only. Shallow pass-throughs are omitted.]

### [TermFromContext]
- **Role**: [one sentence using domain vocabulary]
- **Interface**: [public API, route, event, or function signature]
- **Key files**: `path/to/file`

## Core Flows

[The 1–2 flows that matter most — auth, primary business operation, etc.]

### [FlowName]

[SEQUENCE DIAGRAM — real endpoint/function names, CONTEXT.md node labels]

## Data Model

[Only if a persistent data layer exists.]

[ER DIAGRAM or class diagram — real model names from the codebase]

## Infrastructure

[Only if docker-compose.yml, Terraform, or k8s manifests exist.]

[DEPLOYMENT DIAGRAM — real service names, actual port numbers if known]

## Key Decisions

[Non-obvious choices that would surprise a new engineer. Skip anything
already in docs/adr/. Offer to create an ADR for decisions that are:
hard to reverse + surprising without context + result of a real trade-off.]

- **[Decision]**: [one sentence rationale]
```

Length limit: 120 lines. If over, cut the shallowest module entry first.

---

### PRODUCT.md

```markdown
# Product

## Problem

[One paragraph: the pain point. Infer from domain terms, UI copy, API shape.]

## Users

[Bullet list. Infer from auth roles, route naming, or README signals.]

## Core Features

[Max 6 bullets. One sentence each. Only features present in the code.]

## Non-Goals

[What this explicitly does not do. Infer from missing features or disclaimers.]

## Status

[Prototype / Active Development / Production / Maintenance / Deprecated]
[Infer from git activity, version field, or package.json signals.]
```

Length limit: 50 lines.

---

### README.md

```markdown
# [Project Name]

[One sentence: what it does and for whom. Use CONTEXT.md vocabulary.]

## Quick Start

[Exact commands only. Copy-paste ready. No paraphrasing.]

## Stack

[Bullet: language · framework · database · infra. One line each.]

## Structure

[File tree, 2 levels. Annotate only non-obvious dirs using domain terms.]

## Contributing

[Link to CONTRIBUTING.md, or 2 sentences max.]
```

Length limit: 80 lines. Omit any section you cannot fill accurately.
No badges unless they already exist. No emoji.

---

## Quality Gates

Before writing, verify each item:

- [ ] Every diagram node label comes from CONTEXT.md or real code names
- [ ] No diagram has placeholder names (ServiceA, Module1, DB, etc.)
- [ ] CONTEXT.md terms are consistent across all four files
- [ ] Sequence diagrams show real method/endpoint names
- [ ] Quick Start commands are copy-pasteable and accurate
- [ ] PRODUCT.md features match actually implemented functionality
- [ ] Key Decisions does not repeat anything already in docs/adr/
- [ ] Line limits respected: README ≤80, ARCHITECTURE ≤120, PRODUCT ≤50
- [ ] No section present that cannot be filled with verified content

If a section fails verification: omit it entirely.
An honest short doc beats a padded inaccurate one.

---

## Update Mode (`--update`)

1. Read existing files first
2. Preserve all sections marked `<!-- manual -->`
3. Cross-reference CONTEXT.md: never rename existing terms
4. Cross-reference docs/adr/: never re-surface resolved decisions
5. Regenerate all other sections from fresh scan
6. Prepend `<!-- generated: YYYY-MM-DD -->` at top of each file
7. Show a one-line diff summary per file before writing

---

## ADR Offer

After generating docs, if you found a non-obvious architectural decision
that is NOT already in docs/adr/, offer:

> "I noticed [decision]. Want me to create an ADR for it?
> It meets the criteria: hard to reverse, surprising without context,
> result of a real trade-off."

Only offer once per session. Don't push it.

ADR format (docs/adr/NNNN-short-title.md):
```
# NNNN — [Decision Title]

**Status**: Accepted  
**Date**: YYYY-MM-DD

## Context
[Why this decision needed to be made.]

## Decision
[What was decided, in one paragraph.]

## Consequences
[What becomes easier. What becomes harder.]
```

---

## Anti-Patterns

- Don't copy content from existing README without verifying it's current
- Don't generate a diagram you can't validate against actual code
- Don't use generic labels in diagrams (ServiceA, Handler, Manager)
- Don't contradict or rename terms already in CONTEXT.md
- Don't surface decisions already resolved in docs/adr/
- Don't add Future Work / Roadmap unless explicitly asked
- Don't write more than one paragraph of prose per section
- Don't invent routes, model names, or module responsibilities