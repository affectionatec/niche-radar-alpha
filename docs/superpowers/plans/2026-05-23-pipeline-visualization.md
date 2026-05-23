# Pipeline Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace plain text pipeline logging with a GitHub Actions-style Rich Live terminal visualization showing stage progression, agent activity, and progress bars.

**Architecture:** A `PipelineDisplay` class in `niche_radar/ui/pipeline_display.py` acts as an observer — it replaces `log_fn=print` with `log_fn=display.log`, parses existing log messages to update internal state, and renders a Rich Live layout. The pipeline engine code gets minimal changes (2 new per-item/per-cluster log lines for progress granularity).

**Tech Stack:** Rich (already installed), threading.Lock for thread safety

---

## Tasks

### Task 1: Add rich dependency
### Task 2: Create PipelineDisplay with state model, log parser, renderer + tests  
### Task 3: Add per-item/per-cluster progress log messages to pipeline.py
### Task 4: Wire PipelineDisplay into CLI analyze command
### Task 5: Final integration test
