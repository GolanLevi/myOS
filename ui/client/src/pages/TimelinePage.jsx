import { Activity, CheckCircle2, Clock3, RefreshCw, TimerReset } from 'lucide-react';
import { useApi } from '../hooks/useApi.js';
import { AGENT_COLORS, STATUS_COLORS, cn, timeAgo } from '../lib/utils.js';
import {
  DashboardEmptyState,
  DashboardHero,
  DashboardMetricCard,
  DashboardPage,
  DashboardPanel,
} from '../components/chrome/DashboardPrimitives.jsx';

const STATUS_LABEL = {
  success: 'Completed',
  approved: 'Approved',
  rejected: 'Rejected',
  pending: 'Waiting',
  failed: 'Failed',
};

export default function TimelinePage() {
  const { data, loading, refresh } = useApi('/api/activity', { params: { limit: 50 } });
  const items = data?.items || [];
  const completedCount = items.filter((item) => ['success', 'approved'].includes(item.status)).length;
  const waitingCount = items.filter((item) => item.status === 'pending').length;

  return (
    <DashboardPage>
      <DashboardHero
        title="Timeline"
        meta={[
          `${data?.total || 0} total actions`,
          `${data?.hoursSaved || 0}h saved`,
        ]}
        actions={
          <button onClick={refresh} className="inline-flex min-h-[40px] items-center gap-2 rounded-[14px] border border-white/7 bg-white/[0.03] px-4 text-[13px] font-medium text-text-secondary">
            <RefreshCw size={14} className={cn(loading && 'animate-spin')} />
            Refresh
          </button>
        }
        stats={[
          <DashboardMetricCard
            key="timeline-total"
            label="Activity"
            value={String(data?.total || 0)}
            sub="Logged actions"
            icon={Activity}
            tone="indigo"
          />,
          <DashboardMetricCard
            key="timeline-waiting"
            label="Waiting"
            value={String(waitingCount)}
            sub="Still pending"
            icon={Clock3}
            tone="amber"
          />,
          <DashboardMetricCard
            key="timeline-completed"
            label="Completed"
            value={String(completedCount)}
            sub="Resolved actions"
            icon={CheckCircle2}
            tone="green"
          />,
          <DashboardMetricCard
            key="timeline-saved"
            label="Hours saved"
            value={`${data?.hoursSaved || 0}h`}
            sub="Operational time recovered"
            icon={TimerReset}
            tone="cyan"
          />,
        ]}
      />

      <DashboardPanel className="p-6">
        {loading ? (
          <div className="space-y-4">{[1, 2, 3, 4, 5].map((i) => <TimelineSkeleton key={i} />)}</div>
        ) : !items.length ? (
          <DashboardEmptyState text="No activity recorded yet." />
        ) : (
          <div className="relative">
            <div className="absolute left-[11px] top-3 bottom-3 w-px bg-border" />
            <div className="space-y-4 pl-8">
              {items.map((item, idx) => {
                const color = AGENT_COLORS[item.agentName] || '#94a3b8';
                const statusCls = STATUS_COLORS[item.status] || 'text-text-muted';

                return (
                  <div key={item._id} className="relative animate-fade-in" style={{ animationDelay: `${idx * 30}ms` }}>
                    <div
                      className="absolute -left-8 mt-0.5 h-[11px] w-[11px] rounded-full border-2 border-bg-primary"
                      style={{ backgroundColor: color }}
                    />
                    <div className="rounded-[22px] border border-white/6 bg-[linear-gradient(180deg,rgba(21,28,43,0.98),rgba(16,21,34,0.98))] px-4 py-3.5 shadow-[0_12px_36px_rgba(0,0,0,0.18)]">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="mb-1.5 flex flex-wrap items-center gap-2">
                            <span
                              className="rounded-full px-2.5 py-1 text-[10px] font-semibold"
                              style={{ backgroundColor: `${color}18`, color }}
                            >
                              {item.agentName}
                            </span>
                            <span className="rounded-full border border-white/8 bg-white/[0.03] px-2.5 py-1 font-mono text-[10px] text-text-muted">
                              {item.action}
                            </span>
                            <span className={cn('text-[10px] font-medium', statusCls)}>
                              {STATUS_LABEL[item.status] || item.status}
                            </span>
                          </div>
                          <p className="text-[14px] leading-6 text-text-primary">{item.description}</p>
                        </div>

                        <div className="text-right text-[11px] text-text-muted">
                          <p className="whitespace-nowrap">{timeAgo(item.createdAt)}</p>
                          {item.minutesSaved > 0 ? (
                            <p className="mt-1 text-accent-green">+{item.minutesSaved}m saved</p>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </DashboardPanel>
    </DashboardPage>
  );
}

function TimelineSkeleton() {
  return (
    <div className="pl-8 relative">
      <div className="absolute left-[3px] mt-1 h-[11px] w-[11px] rounded-full bg-border" />
      <div className="rounded-[22px] border border-white/6 bg-bg-card/70 p-3.5 animate-pulse space-y-2">
        <div className="flex gap-2">
          <div className="h-4 rounded bg-bg-hover w-20" />
          <div className="h-4 rounded bg-bg-hover w-24" />
        </div>
        <div className="h-3 rounded bg-bg-hover w-3/4" />
      </div>
    </div>
  );
}
