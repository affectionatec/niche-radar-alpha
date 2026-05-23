'use client';

import { useRef, useEffect, useState } from 'react';
import { color, font, fontSize as fs } from '@/lib/tokens';

interface ActivityLogProps {
  logs: string[];
  isRunning: boolean;
}

function classifyLine(line: string): 'phase' | 'agent' | 'error' | 'info' | 'normal' {
  if (/^phase=[ABCD]/.test(line) || /^pipeline_(run|done|skipped|aborted)/.test(line) || /^===\s+\w+\s+===/.test(line)) return 'phase';
  if (/^A[1-8]=/.test(line) || /^CLUSTER_DONE/.test(line) || /^CLUSTERING/.test(line)) return 'agent';
  if (/FAIL|ERROR|failed/.test(line)) return 'error';
  if (/^phase_[ac]_/.test(line) || /^momentum_/.test(line) || /^cluster=/.test(line)) return 'info';
  return 'normal';
}

const LINE_COLORS: Record<ReturnType<typeof classifyLine>, string> = {
  phase: 'rgba(255,255,255,0.85)',
  agent: 'rgba(255,255,255,0.55)',
  error: color.error,
  info: color.fgDisabled,
  normal: 'rgba(255,255,255,0.45)',
};

export default function ActivityLog({ logs, isRunning }: ActivityLogProps) {
  const [expanded, setExpanded] = useState(false);
  const [filter, setFilter] = useState('');
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (expanded && !filter) {
      endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs.length, expanded, filter]);

  if (logs.length === 0) return null;

  const filteredLogs = filter
    ? logs.filter(l => l.toLowerCase().includes(filter.toLowerCase()))
    : logs;

  return (
    <div style={{ background: color.surface, border: `1px solid ${color.border}` }}>
      <button
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        aria-controls="activity-log-content"
        style={{
          width: '100%',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 20px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          borderBottom: expanded ? `1px solid rgba(255,255,255,0.06)` : 'none',
        }}
      >
        <span style={{ fontFamily: font.mono, fontSize: fs.sm, letterSpacing: '1px', color: color.fgGhost, textTransform: 'uppercase' }}>
          {expanded ? '▼' : '▶'} Activity Log
        </span>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span style={{ fontFamily: font.mono, fontSize: fs.sm, color: color.fgGhost }}>
            {logs.length} lines
          </span>
          {isRunning && (
            <span style={{
              fontFamily: font.mono,
              fontSize: fs.xs,
              color: color.success,
              letterSpacing: '0.5px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}>
              <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: color.success, display: 'inline-block' }} />
              LIVE
            </span>
          )}
        </div>
      </button>

      {expanded && (
        <div id="activity-log-content" role="log" aria-label="Pipeline activity log">
          {/* Filter bar */}
          <div style={{ padding: '8px 20px', borderBottom: `1px solid rgba(255,255,255,0.04)` }}>
            <input
              type="search"
              placeholder="Filter logs..."
              value={filter}
              onChange={e => setFilter(e.target.value)}
              aria-label="Filter log lines"
              style={{
                background: color.surfaceHover,
                border: `1px solid ${color.border}`,
                color: color.fg,
                fontFamily: font.mono,
                fontSize: fs.sm,
                padding: '6px 10px',
                width: '100%',
                maxWidth: '300px',
                outline: 'none',
              }}
            />
          </div>

          <div style={{ maxHeight: '360px', overflowY: 'auto', padding: '12px 20px' }}>
            {filteredLogs.map((line, i) => {
              const type = classifyLine(line);
              return (
                <div key={i} style={{
                  fontFamily: font.mono,
                  fontSize: fs.base,
                  lineHeight: '1.7',
                  color: LINE_COLORS[type],
                  fontWeight: type === 'phase' ? 500 : 400,
                  ...(type === 'phase' && i > 0 ? { marginTop: '6px' } : {}),
                }}>
                  {line || ' '}
                </div>
              );
            })}
            <div ref={endRef} />
          </div>
        </div>
      )}
    </div>
  );
}
