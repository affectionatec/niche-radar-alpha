'use client';

import { useMemo } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PhaseId = 'A' | 'B' | 'C' | 'D';
export type PhaseStatus = 'pending' | 'running' | 'done' | 'failed' | 'skipped';
export type StepId = 'collect' | 'analyze' | 'report';

export interface PhaseProgress {
  current: number;
  total: number;
}

export interface PhaseState {
  id: PhaseId;
  name: string;
  description: string;
  status: PhaseStatus;
  progress: PhaseProgress | null;
  stats: Record<string, string | number>;
}

export interface AgentEvent {
  agent: string;
  action: string;
  detail: string;
  timestamp: number; // index in log array
}

export interface RunAllStep {
  step: StepId;
  status: PhaseStatus;
}

export interface PipelineSummary {
  items: number;
  passed: number;
  clusters: number;
  persisted: number;
  budgetUsed: number;
}

export interface PipelineState {
  runId: string | null;
  totalItems: number;
  budget: number;
  currentRunAllStep: StepId | null;
  runAllSteps: RunAllStep[];
  isRunAll: boolean;
  phases: Record<PhaseId, PhaseState>;
  agents: AgentEvent[];
  isRunning: boolean;
  isComplete: boolean;
  isFailed: boolean;
  summary: PipelineSummary | null;
  clusterResults: { clusterId: string; verdict: string; score: string; tier: string; niche: string }[];
}

// ---------------------------------------------------------------------------
// Default state factory
// ---------------------------------------------------------------------------

function defaultPhases(): Record<PhaseId, PhaseState> {
  return {
    A: { id: 'A', name: 'FILTER & EXTRACT', description: 'A1 relevance → A2 extraction', status: 'pending', progress: null, stats: {} },
    B: { id: 'B', name: 'CLUSTER', description: 'Group by pain similarity', status: 'pending', progress: null, stats: {} },
    C: { id: 'C', name: 'DEEP ANALYSIS', description: 'A3→A8 per cluster', status: 'pending', progress: null, stats: {} },
    D: { id: 'D', name: 'PERSIST', description: 'Write niche candidates', status: 'pending', progress: null, stats: {} },
  };
}

function defaultState(): PipelineState {
  return {
    runId: null,
    totalItems: 0,
    budget: 0,
    currentRunAllStep: null,
    runAllSteps: [],
    isRunAll: false,
    phases: defaultPhases(),
    agents: [],
    isRunning: false,
    isComplete: false,
    isFailed: false,
    summary: null,
    clusterResults: [],
  };
}

// ---------------------------------------------------------------------------
// Log line parsers
// ---------------------------------------------------------------------------

const RE_PIPELINE_RUN = /^pipeline_run=(\S+)\s+items=(\d+)\s+budget=(\d+)/;
const RE_PHASE_A_START = /^phase=A\s+items=(\d+)/;
const RE_PHASE_A_ITEM = /^phase_a_item=(\d+)\/(\d+)/;
const RE_PHASE_A_DONE = /^phase=A\s+done\s+passed=(\d+)\s+rejected=(\d+)/;
const RE_PHASE_B_START = /^phase=B\s+extractions=(\d+)/;
const RE_PHASE_B_SKIP = /^phase=B\s+skip\s+empty/;
const RE_PHASE_C_START = /^phase=C\s+clusters=(\d+)/;
const RE_PHASE_C_ITEM = /^phase_c_cluster=(\d+)\/(\d+)/;
const RE_PHASE_C_DONE = /^phase=C\s+done/;
const RE_PHASE_D_START = /^phase=D\s+persisting\s+(\d+)/;
const RE_PHASE_D_DRY = /^phase=D\s+dry_run/;
const RE_PIPELINE_DONE = /^pipeline_done\s/;
const RE_PIPELINE_SKIP = /^pipeline_skipped/;
const RE_PIPELINE_ABORT = /^pipeline_aborted/;
const RE_A1_PASS = /^A1=PASS\s+conf=([\d.]+)\s+type=(\S+)/;
const RE_A1_REJECT = /^A1=REJECT/;
const RE_A2_DONE = /^A2=DONE/;
const RE_CLUSTER_DONE = /^CLUSTER_DONE\s+verdict=(\S+)\s+score=(\S+)/;
const RE_CLUSTERING = /^CLUSTERING\s+(.*)/;
const RE_CLUSTER_RESULT = /^cluster=(\S+)\s+verdict=(\S+)\s+score=(\S+)\s+tier=(\S+)\s+niche=(.+)/;
const RE_RUN_ALL_STEP = /^===\s+(\w+)\s+===/;
const RE_MOMENTUM = /^momentum_updated\s+niches=(\d+)/;
const RE_AGENT_FAIL = /^(\w+)=FAIL\s+reason=(.*)/;
const RE_WEB_VALIDATION = /^cluster=(\S+)\s+web_validation=(\S+)/;

/**
 * Parse an array of log lines into a structured PipelineState.
 * Pure function — no side effects.
 */
export function parseLogs(logs: string[], jobStep?: string): PipelineState {
  const state = defaultState();
  if (!logs || logs.length === 0) return state;

  const isRunAll = jobStep === 'run-all';
  state.isRunAll = isRunAll;

  if (isRunAll) {
    state.runAllSteps = [
      { step: 'collect', status: 'pending' },
      { step: 'analyze', status: 'pending' },
      { step: 'report', status: 'pending' },
    ];
  }

  let m: RegExpMatchArray | null;

  for (let i = 0; i < logs.length; i++) {
    const line = logs[i].trim();

    // Run-all step markers
    if ((m = line.match(RE_RUN_ALL_STEP))) {
      const stepName = m[1].toLowerCase() as StepId;
      state.currentRunAllStep = stepName;
      // Mark previous steps as done, current as running
      for (const s of state.runAllSteps) {
        if (s.step === stepName) {
          s.status = 'running';
        } else if (s.status === 'running') {
          s.status = 'done';
        }
      }
      // Reset phases when entering analyze step
      if (stepName === 'analyze') {
        state.phases = defaultPhases();
      }
      continue;
    }

    // Pipeline start
    if ((m = line.match(RE_PIPELINE_RUN))) {
      state.runId = m[1];
      state.totalItems = parseInt(m[2]);
      state.budget = parseInt(m[3]);
      state.isRunning = true;
      continue;
    }

    // Phase A
    if ((m = line.match(RE_PHASE_A_START))) {
      state.phases.A.status = 'running';
      state.phases.A.progress = { current: 0, total: parseInt(m[1]) };
      continue;
    }
    if ((m = line.match(RE_PHASE_A_ITEM))) {
      state.phases.A.progress = { current: parseInt(m[1]), total: parseInt(m[2]) };
      continue;
    }
    if ((m = line.match(RE_PHASE_A_DONE))) {
      state.phases.A.status = 'done';
      state.phases.A.stats.passed = parseInt(m[1]);
      state.phases.A.stats.rejected = parseInt(m[2]);
      if (state.phases.A.progress) {
        state.phases.A.progress.current = state.phases.A.progress.total;
      }
      continue;
    }

    // Agent events (A1, A2)
    if ((m = line.match(RE_A1_PASS))) {
      state.agents.push({ agent: 'A1', action: 'PASS', detail: `conf=${m[1]} type=${m[2]}`, timestamp: i });
      if (!state.phases.A.stats.a1Pass) state.phases.A.stats.a1Pass = 0;
      state.phases.A.stats.a1Pass = (state.phases.A.stats.a1Pass as number) + 1;
      continue;
    }
    if (RE_A1_REJECT.test(line)) {
      state.agents.push({ agent: 'A1', action: 'REJECT', detail: line.replace('A1=REJECT ', ''), timestamp: i });
      if (!state.phases.A.stats.a1Reject) state.phases.A.stats.a1Reject = 0;
      state.phases.A.stats.a1Reject = (state.phases.A.stats.a1Reject as number) + 1;
      continue;
    }
    if (RE_A2_DONE.test(line)) {
      state.agents.push({ agent: 'A2', action: 'DONE', detail: 'extraction complete', timestamp: i });
      continue;
    }

    // Phase B
    if ((m = line.match(RE_PHASE_B_START))) {
      state.phases.B.status = 'running';
      state.phases.B.stats.extractions = parseInt(m[1]);
      continue;
    }
    if (RE_PHASE_B_SKIP.test(line)) {
      state.phases.B.status = 'skipped';
      continue;
    }
    if ((m = line.match(RE_CLUSTERING))) {
      state.agents.push({ agent: 'CLUSTER', action: 'CLUSTER', detail: m[1], timestamp: i });
      // If we see clustering output, B is running or done
      if (line.includes('final_clusters=')) {
        const fc = line.match(/final_clusters=(\d+)/);
        if (fc) state.phases.B.stats.clusters = parseInt(fc[1]);
        state.phases.B.status = 'done';
      }
      continue;
    }

    // Phase C
    if ((m = line.match(RE_PHASE_C_START))) {
      state.phases.B.status = 'done'; // B must be done if C starts
      state.phases.C.status = 'running';
      state.phases.C.progress = { current: 0, total: parseInt(m[1]) };
      continue;
    }
    if ((m = line.match(RE_PHASE_C_ITEM))) {
      state.phases.C.progress = { current: parseInt(m[1]), total: parseInt(m[2]) };
      continue;
    }
    if ((m = line.match(RE_CLUSTER_DONE))) {
      state.agents.push({ agent: 'A3-A8', action: 'CLUSTER_DONE', detail: `verdict=${m[1]} score=${m[2]}`, timestamp: i });
      continue;
    }
    if (RE_PHASE_C_DONE.test(line)) {
      state.phases.C.status = 'done';
      if (state.phases.C.progress) {
        state.phases.C.progress.current = state.phases.C.progress.total;
      }
      continue;
    }

    // Phase D
    if ((m = line.match(RE_PHASE_D_START))) {
      state.phases.D.status = 'running';
      state.phases.D.stats.totalClusters = parseInt(m[1]);
      continue;
    }
    if (RE_PHASE_D_DRY.test(line)) {
      state.phases.D.status = 'skipped';
      continue;
    }
    if ((m = line.match(RE_CLUSTER_RESULT))) {
      state.clusterResults.push({
        clusterId: m[1],
        verdict: m[2],
        score: m[3],
        tier: m[4],
        niche: m[5],
      });
      continue;
    }
    if ((m = line.match(RE_WEB_VALIDATION))) {
      state.agents.push({ agent: 'A7', action: 'WEB_VALIDATE', detail: `cluster=${m[1]} verdict=${m[2]}`, timestamp: i });
      continue;
    }

    // Pipeline terminal states
    if (RE_PIPELINE_DONE.test(line)) {
      state.phases.D.status = 'done';
      state.isComplete = true;
      state.isRunning = false;
      // Mark current run-all step as done
      if (isRunAll && state.currentRunAllStep === 'analyze') {
        const s = state.runAllSteps.find(rs => rs.step === 'analyze');
        if (s) s.status = 'done';
      }
      // Try to parse summary
      const jsonPart = line.replace('pipeline_done ', '');
      try {
        const parsed = JSON.parse(jsonPart.replace(/'/g, '"'));
        state.summary = {
          items: parsed.items ?? 0,
          passed: parsed.passed ?? 0,
          clusters: parsed.clusters ?? 0,
          persisted: parsed.persisted ?? 0,
          budgetUsed: parsed.budget_used ?? 0,
        };
      } catch {
        // summary parsing is best-effort
      }
      continue;
    }
    if (RE_PIPELINE_SKIP.test(line)) {
      state.isComplete = true;
      state.isRunning = false;
      continue;
    }
    if (RE_PIPELINE_ABORT.test(line)) {
      state.isFailed = true;
      state.isRunning = false;
      continue;
    }

    // Agent failures
    if ((m = line.match(RE_AGENT_FAIL))) {
      state.agents.push({ agent: m[1], action: 'FAIL', detail: m[2], timestamp: i });
      continue;
    }

    // Momentum update
    if ((m = line.match(RE_MOMENTUM))) {
      state.agents.push({ agent: 'MOMENTUM', action: 'UPDATE', detail: `${m[1]} niches`, timestamp: i });
      continue;
    }
  }

  // Mark final run-all step as done if job is complete
  if (isRunAll && !state.isRunning) {
    for (const s of state.runAllSteps) {
      if (s.status === 'running') {
        s.status = state.isFailed ? 'failed' : 'done';
      }
    }
  }

  return state;
}

// ---------------------------------------------------------------------------
// React hook
// ---------------------------------------------------------------------------

export function usePipelineState(logs: string[] | undefined, jobStep?: string): PipelineState {
  return useMemo(() => parseLogs(logs ?? [], jobStep), [logs, jobStep]);
}
