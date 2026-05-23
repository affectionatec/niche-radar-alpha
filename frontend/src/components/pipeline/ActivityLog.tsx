'use client';

import { useRef, useEffect, useState } from 'react';

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

function lineColor(type: ReturnType<typeof classifyLine>): string {
  switch (type) {
    case 'phase': return 'rgba(255,255,255,0.85)';
    case 'agent': return 'rgba(255,255,255,0.55)';
    case 'error': return 'rgba(255,80,80,0.8)';
    case 'info': return 'rgba(255,255,255,0.35)';
    default: return 'rgba(255,255,255,0.45)';
  }
}

export default function ActivityLog({ logs, isRunning }: ActivityLogProps) {
  const [expanded, setExpanded] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (expanded) {
      endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs.length, expanded]);

  if (logs.length === 0) return null;

  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.08)',
    }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          width: '100%',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 20px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          borderBottom: expanded ? '1px solid rgba(255,255,255,0.06)' : 'none',
        }}
      >
        <span style={{
          fontFamily: 'var(--font-geist-mono)',
          fontSize: '10px',
          letterSpacing: '1px',
          color: 'rgba(255,255,255,0.3)',
          textTransform: 'uppercase',
        }}>
          {expanded ? '▼' : '▶'} Activity Log
        </span>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '10px',
            color: 'rgba(255,255,255,0.2)',
          }}>
            {logs.length} lines
          </span>
          {isRunning && (
            <span style={{
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '9px',
              color: 'rgba(255,255,255,0.4)',
              letterSpacing: '0.5px',
            }}>
              LIVE
            </span>
          )}
        </div>
      </button>

      {expanded && (
        <div style={{
          maxHeight: '360px',
          overflowY: 'auto',
          padding: '12px 20px',
        }}>
          {logs.map((line, i) => {
            const type = classifyLine(line);
            return (
              <div key={i} style={{
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '11px',
                lineHeight: '1.7',
                color: lineColor(type),
                fontWeight: type === 'phase' ? 500 : 400,
                ...(type === 'phase' && i > 0 ? { marginTop: '6px' } : {}),
              }}>
                {line || ' '}
              </div>
            );
          })}
          <div ref={endRef} />
        </div>
      )}
    </div>
  );
}
