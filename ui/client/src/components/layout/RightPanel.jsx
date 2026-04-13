import { useApi } from '../../hooks/useApi.js';
import { timeAgo, STATUS_COLORS, AGENT_COLORS, cn } from '../../lib/utils.js';
import { Activity, Wifi, WifiOff, RefreshCw, ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';

const STATUS_LABEL = {
  success:  'Completed',
  approved: 'Approved',
  rejected: 'Rejected',
  pending:  'Waiting',
  failed:   'Failed',
};

export default function RightPanel() {
  const { data: activityData, loading, refresh } = useApi('/api/activity', { params: { limit: 8 } });
  const { data: agents } = useApi('/api/agents');

  const items   = activityData?.items || [];
  const online  = agents?.filter(a => a.status === 'active').length || 0;

  return (
    <aside className="w-[280px] flex-shrink-0 border-l border-border flex flex-col h-full overflow-hidden bg-bg-secondary">

      {/* Recent Activity */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity size={13} className="text-text-muted" />
            <span className="section-title">Recent Activity</span>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={refresh} className="btn-ghost p-1" title="Refresh">
              <RefreshCw size={11} className={cn('text-text-muted', loading && 'animate-spin')} />
            </button>
            <Link to="/timeline" className="btn-ghost p-1" title="View all">
              <ChevronRight size={11} className="text-text-muted" />
            </Link>
          </div>
        </div>

        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-2.5">
                <div className="w-1.5 h-1.5 rounded-full bg-border mt-1.5 flex-shrink-0" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-2.5 bg-bg-hover rounded w-4/5 animate-pulse" />
                  <div className="h-2 bg-bg-hover rounded w-2/5 animate-pulse" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => {
              const color = AGENT_COLORS[item.agentName] || '#94a3b8';
              const statusCls = STATUS_COLORS[item.status] || 'text-text-muted';
              return (
                <div key={item._id} className="flex gap-2.5 group">
                  <div className="relative mt-1 flex-shrink-0">
                    <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />
                    <div className="absolute top-2 left-[2px] w-px h-full" style={{ backgroundColor: color, opacity: 0.15 }} />
                  </div>
                  <div className="flex-1 pb-3 border-b border-border/50 last:border-0">
                    <p className="text-xs text-text-primary leading-snug">{item.description}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className={cn('text-[10px] font-medium', statusCls)}>
                        {STATUS_LABEL[item.status] || item.status}
                      </span>
                      <span className="text-[10px] text-text-muted">·</span>
                      <span className="text-[10px] text-text-muted">{timeAgo(item.createdAt)}</span>
                      {item.minutesSaved > 0 && (
                        <>
                          <span className="text-[10px] text-text-muted">·</span>
                          <span className="text-[10px] text-accent-green">+{item.minutesSaved}m saved</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            {items.length === 0 && (
              <p className="text-text-muted text-xs text-center py-4">No activity yet</p>
            )}
          </div>
        )}
      </div>

      {/* System Status */}
      <div className="border-t border-border p-4 space-y-3">
        <span className="section-title">System Status</span>
        <div className="card p-3 space-y-2 mt-2">
          <StatusRow label="myOS Server"   status="online" />
          <StatusRow label="MongoDB"        status="online" />
          <StatusRow label="LangGraph"      status="online" />
          <StatusRow label="Telegram Bot"   status="idle" />
        </div>
        <div className="flex items-center gap-1.5 mt-1">
          <div className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse-dot" />
          <span className="text-[11px] text-text-muted">
            {online} agent{online !== 1 ? 's' : ''} online
          </span>
        </div>
      </div>
    </aside>
  );
}

function StatusRow({ label, status }) {
  const isOnline = status === 'online';
  const isIdle   = status === 'idle';
  return (
    <div className="flex items-center justify-between">
      <span className="text-[11px] text-text-secondary">{label}</span>
      <div className="flex items-center gap-1.5">
        <div className={cn(
          'w-1.5 h-1.5 rounded-full',
          isOnline ? 'bg-accent-green' : isIdle ? 'bg-accent-amber' : 'bg-accent-red'
        )} />
        <span className={cn(
          'text-[10px] font-medium',
          isOnline ? 'text-accent-green' : isIdle ? 'text-accent-amber' : 'text-accent-red'
        )}>
          {status}
        </span>
      </div>
    </div>
  );
}
