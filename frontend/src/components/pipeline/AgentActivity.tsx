'use client';

import { AgentEvent } from '@/lib/usePipelineState';
import { color, font, fontSize } from '@/lib/tokens';

interface AgentActivityProps {
  agents: AgentEvent[];
  maxDisplay?: number;
}

function agentColor(action: string): string {
  if (action === 'PASS') return color.fgSecondary;
  if (action === 'REJECT') return color.fgDisabled;
  if (action === 'FAIL') return color.errorMuted;
  if (action === 'CLUSTER_DONE') return color.fgMuted;
  if (action === 'WEB_VALIDATE') return color.fgMuted;
  return color.fgMuted;
}

const ACTION_ICONS: Record<string, { icon: string; label: string }> = {
  PASS: { icon: '✓', label: 'Passed' },
  REJECT: { icon: '✗', label: 'Rejected' },
  FAIL: { icon: '✗', label: 'Failed' },
  DONE: { icon: '✓', label: 'Done' },
  CLUSTER_DONE: { icon: '◆', label: 'Cluster done' },
  WEB_VALIDATE: { icon: '◎', label: 'Web validate' },
  CLUSTER: { icon: '◇', label: 'Clustering' },
  UPDATE: { icon: '↻', label: 'Updated' },
};

export default function AgentActivity({ agents, maxDisplay = 12 }: AgentActivityProps) {
  if (agents.length === 0) return null;

  const recentAgents = agents.slice(-maxDisplay);
  const hasMore = agents.length > maxDisplay;

  return (
    <div
      role="log"
      aria-label="Agent activity"
      style={{ background: color.surface, border: `1px solid ${color.border}`, padding: '16px 20px' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <span style={{ fontFamily: font.mono, fontSize: fontSize.sm, letterSpacing: '1px', color: color.fgGhost, textTransform: 'uppercase' }}>
          Agent Activity
        </span>
        <span style={{ fontFamily: font.mono, fontSize: fontSize.sm, color: color.fgGhost }}>
          {agents.length} events
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {hasMore && (
          <div style={{ fontFamily: font.mono, fontSize: fontSize.sm, color: 'rgba(255,255,255,0.15)', paddingBottom: '4px' }}>
            ··· {agents.length - maxDisplay} earlier events
          </div>
        )}
        {recentAgents.map((event, i) => {
          const actionInfo = ACTION_ICONS[event.action] || { icon: '·', label: event.action };
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingLeft: '4px' }}>
              <span
                aria-label={actionInfo.label}
                style={{ fontFamily: font.mono, fontSize: fontSize.base, color: agentColor(event.action), width: '14px', textAlign: 'center', flexShrink: 0 }}
              >
                {actionInfo.icon}
              </span>
              <span style={{ fontFamily: font.mono, fontSize: fontSize.base, color: color.fgMuted, letterSpacing: '0.5px', width: '44px', flexShrink: 0 }}>
                {event.agent}
              </span>
              <span style={{ fontFamily: font.mono, fontSize: fontSize.sm, color: color.fgGhost, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {event.detail}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
