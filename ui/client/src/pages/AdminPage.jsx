import { useState } from 'react';
import { useApi, useMutation } from '../hooks/useApi.js';
import { timeAgo, AGENT_COLORS, cn } from '../lib/utils.js';
import { Bot, Play, Pause, RefreshCw, Plus, Loader2, MoreHorizontal } from 'lucide-react';

const STATUS_CONFIG = {
  active: { label: 'Active',  dot: 'bg-accent-green',  text: 'text-accent-green'  },
  idle:   { label: 'Idle',    dot: 'bg-text-muted',    text: 'text-text-muted'    },
  paused: { label: 'Paused',  dot: 'bg-accent-amber',  text: 'text-accent-amber'  },
  error:  { label: 'Error',   dot: 'bg-accent-red',    text: 'text-accent-red'    },
};

export default function AdminPage() {
  const { data: agents, loading, refresh } = useApi('/api/agents');
  const { data: stats } = useApi('/api/agents/stats');
  const { mutate: updateAgent } = useMutation('patch', '/api/agents');
  const [busy, setBusy] = useState(null);

  const toggleStatus = async (agent) => {
    setBusy(agent._id);
    const newStatus = agent.status === 'active' ? 'paused' : 'active';
    try {
      await updateAgent({ status: newStatus }, `/${agent._id}`);
      refresh();
    } finally { setBusy(null); }
  };

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary">Agent Admin</h1>
          <p className="text-sm text-text-muted mt-0.5">Manage your AI agent fleet</p>
        </div>
        <button onClick={refresh} className="btn-ghost">
          <RefreshCw size={13} className={cn(loading && 'animate-spin')} />
        </button>
      </div>

      {/* Fleet stats */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Total',   value: stats?.total  || 0, color: 'text-text-primary'  },
          { label: 'Active',  value: stats?.active  || 0, color: 'text-accent-green'  },
          { label: 'Paused',  value: stats?.paused  || 0, color: 'text-accent-amber'  },
          { label: 'Error',   value: stats?.error   || 0, color: 'text-accent-red'    },
        ].map(s => (
          <div key={s.label} className="card p-4 text-center">
            <p className={cn('text-3xl font-semibold', s.color)}>{s.value}</p>
            <p className="text-[10px] text-text-muted uppercase tracking-widest mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Agent list */}
      {loading ? (
        <div className="space-y-3">{[1,2,3,4].map(i => <div key={i} className="card p-5 animate-pulse h-20" />)}</div>
      ) : (
        <div className="space-y-3">
          {agents?.map(agent => {
            const sc = STATUS_CONFIG[agent.status] || STATUS_CONFIG.idle;
            const agentColor = agent.color || AGENT_COLORS[agent.type] || '#6366f1';
            return (
              <div key={agent._id} className="card-hover p-4 animate-fade-in">
                <div className="flex items-start gap-4">
                  {/* Color indicator */}
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: `${agentColor}18` }}
                  >
                    <Bot size={18} style={{ color: agentColor }} />
                  </div>

                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-text-primary">{agent.name}</p>
                      <div className="flex items-center gap-1.5">
                        <div className={cn('w-1.5 h-1.5 rounded-full', sc.dot)} />
                        <span className={cn('text-[10px] font-medium', sc.text)}>{sc.label}</span>
                      </div>
                    </div>
                    <p className="text-xs text-text-muted">{agent.description}</p>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-[10px] text-text-muted font-mono bg-bg-hover px-1.5 py-0.5 rounded">{agent.type}</span>
                      {agent.lastAction && (
                        <span className="text-[10px] text-text-muted truncate max-w-[200px]">
                          Last: {agent.lastAction}
                        </span>
                      )}
                      {agent.lastRun && (
                        <span className="text-[10px] text-text-muted">{timeAgo(agent.lastRun)}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 mt-1">
                      <span className="text-[10px] text-text-muted">
                        <span className="text-text-secondary font-medium">{agent.actionsToday}</span> actions today
                      </span>
                      <span className="text-[10px] text-text-muted">
                        <span className="text-text-secondary font-medium">{agent.totalActions}</span> total
                      </span>
                      {agent.costToday > 0 && (
                        <span className="text-[10px] text-accent-amber">
                          ${agent.costToday.toFixed(4)} today
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => toggleStatus(agent)}
                      disabled={busy === agent._id}
                      className={cn(
                        'btn-secondary h-8 text-[11px]',
                        agent.status === 'active' && 'text-accent-amber border-accent-amber/20 hover:border-accent-amber/40'
                      )}
                    >
                      {busy === agent._id
                        ? <Loader2 size={11} className="animate-spin" />
                        : agent.status === 'active'
                        ? <><Pause size={11} /> Pause</>
                        : <><Play  size={11} /> Resume</>}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
