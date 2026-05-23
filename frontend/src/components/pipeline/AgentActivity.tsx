'use client';

import { AgentEvent } from '@/lib/usePipelineState';

interface AgentActivityProps {
  agents: AgentEvent[];
  maxDisplay?: number;
}

function agentColor(action: string): string {
  if (action === 'PASS') return 'rgba(255,255,255,0.7)';
  if (action === 'REJECT') return 'rgba(255,255,255,0.35)';
  if (action === 'FAIL') return 'rgba(255,80,80,0.7)';
  if (action === 'CLUSTER_DONE') return 'rgba(255,255,255,0.6)';
  if (action === 'WEB_VALIDATE') return 'rgba(255,255,255,0.5)';
  return 'rgba(255,255,255,0.5)';
}

function actionIcon(action: string): string {
  if (action === 'PASS') return '✓';
  if (action === 'REJECT') return '✗';
  if (action === 'FAIL') return '✗';
  if (action === 'DONE') return '✓';
  if (action === 'CLUSTER_DONE') return '◆';
  if (action === 'WEB_VALIDATE') return '◎';
  if (action === 'CLUSTER') return '◇';
  if (action === 'UPDATE') return '↻';
  return '·';
}

export default function AgentActivity({ agents, maxDisplay = 12 }: AgentActivityProps) {
  if (agents.length === 0) return null;

  // Show most recent events
  const recentAgents = agents.slice(-maxDisplay);
  const hasMore = agents.length > maxDisplay;

  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.08)',
      padding: '16px 20px',
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '12px',
      }}>
        <span style={{
          fontFamily: 'var(--font-geist-mono)',
          fontSize: '10px',
          letterSpacing: '1px',
          color: 'rgba(255,255,255,0.3)',
          textTransform: 'uppercase',
        }}>
          Agent Activity
        </span>
        <span style={{
          fontFamily: 'var(--font-geist-mono)',
          fontSize: '10px',
          color: 'rgba(255,255,255,0.2)',
        }}>
          {agents.length} events
        </span>
      </div>

      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
      }}>
        {hasMore && (
          <div style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '10px',
            color: 'rgba(255,255,255,0.15)',
            paddingBottom: '4px',
          }}>
            ··· {agents.length - maxDisplay} earlier events
          </div>
        )}
        {recentAgents.map((event, i) => (
          <div key={i} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            paddingLeft: '4px',
          }}>
            <span style={{
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '11px',
              color: agentColor(event.action),
              width: '14px',
              textAlign: 'center',
              flexShrink: 0,
            }}>
              {actionIcon(event.action)}
            </span>
            <span style={{
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '11px',
              color: 'rgba(255,255,255,0.5)',
              letterSpacing: '0.5px',
              width: '44px',
              flexShrink: 0,
            }}>
              {event.agent}
            </span>
            <span style={{
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '10px',
              color: 'rgba(255,255,255,0.3)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
              {event.detail}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
