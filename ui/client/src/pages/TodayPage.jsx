import { useState } from 'react';
import { format } from 'date-fns';
import { useApi, useMutation } from '../hooks/useApi.js';
import { formatCost, pickBestSummary } from '../lib/utils.js';
import { useAuth } from '../context/AuthContext.jsx';
import { BellRing, Bot, Coins, TimerReset } from 'lucide-react';
import { DashboardEmptyState, DashboardMetricCard, DashboardPage } from '../components/chrome/DashboardPrimitives.jsx';
import ApprovalDrawer from '../components/Approvals/ApprovalDrawer.jsx';
import TodayDecisionCard from '../components/Approvals/TodayDecisionCard.jsx';

const compareDashboardItems = (left, right) => {
  const actionableDelta = Number(Boolean(right?.isActionable)) - Number(Boolean(left?.isActionable));
  if (actionableDelta !== 0) return actionableDelta;

  const freshDelta = Number((right?.freshnessBoost || 0) > 0) - Number((left?.freshnessBoost || 0) > 0);
  if (freshDelta !== 0) return freshDelta;

  const createdDelta = String(right?.createdAt || '').localeCompare(String(left?.createdAt || ''));
  if (createdDelta !== 0) return createdDelta;

  return Number(right?.sortRank || right?.urgencyScore || 0) - Number(left?.sortRank || left?.urgencyScore || 0);
};

const URGENCY_SECTIONS = [
  {
    key: 'needs_decision_now',
    title: 'Needs Decision Now',
  },
  {
    key: 'today',
    title: 'For Today',
  },
  {
    key: 'can_wait',
    title: 'Can Wait',
  },
];

export default function TodayPage() {
  const { user } = useAuth();
  const today = format(new Date(), 'EEEE, MMMM d');
  const { data: notifications, refresh: refreshNotifications, loading: loadingNotifications } = useApi('/api/notifications');
  const { data: approvals, refresh: refreshApprovals, loading: loadingApprovals } = useApi('/api/approvals', { params: { status: 'pending' } });
  const { data: agentStats } = useApi('/api/agents/stats');
  const { data: financeStats } = useApi('/api/finances/stats');
  const { data: activityData } = useApi('/api/activity', { params: { limit: 1 } });
  const { mutate: dismissNotification } = useMutation('delete', '/api/notifications');
  const { mutate: dismissApproval } = useMutation('delete', '/api/approvals');

  const [selectedApproval, setSelectedApproval] = useState(null);

  const notificationItems = Array.isArray(notifications) ? notifications : [];
  const approvalItems = Array.isArray(approvals) ? approvals : [];
  const attentionItems = buildAttentionItems(approvalItems, notificationItems);
  const attentionBuckets = bucketAttentionItems(attentionItems);
  const totalAttention = attentionItems.length;
  const loadingAttention = loadingNotifications || loadingApprovals;
  const visibleSections = loadingAttention
    ? URGENCY_SECTIONS
    : URGENCY_SECTIONS.filter((section) => attentionBuckets[section.key]?.length > 0);
  const greeting = getGreeting();
  const firstName = user?.name?.split(' ')?.[0] || 'there';

  const handleRefresh = () => {
    refreshNotifications();
    refreshApprovals();
  };

  const handleDismiss = async (item) => {
    if (!item?._id) return;

    if (item.kind === 'notification') {
      await dismissNotification({}, `/${item._id}`);
      refreshNotifications();
      return;
    }

    await dismissApproval({}, `/${item._id}`);
    refreshApprovals();
  };

  return (
    <DashboardPage>
      <section className="overflow-hidden rounded-[28px] border border-white/6 bg-[linear-gradient(180deg,rgba(17,22,34,0.92),rgba(10,14,22,0.98))] shadow-[0_18px_60px_rgba(0,0,0,0.32)]">
        <div className="flex flex-col gap-5 px-6 py-6 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="mb-2 text-[12px] font-medium uppercase tracking-[0.18em] text-[#7f8aa3]">
              {greeting}, {firstName}
            </div>
            <h1 className="text-[2.45rem] font-semibold leading-none tracking-[-0.05em] text-text-primary">
              Today
            </h1>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px] text-[#90a0be]">
              <span>{today}</span>
              <span>{totalAttention} items currently need attention</span>
            </div>
          </div>

          <div className="flex gap-2">
            <button className="inline-flex min-h-[40px] items-center rounded-[14px] border border-white/7 bg-white/[0.03] px-4 text-[13px] font-medium text-text-secondary">
              All approvals
            </button>
            <button
              onClick={handleRefresh}
              className="inline-flex min-h-[40px] items-center rounded-[14px] border border-white/7 bg-white/[0.03] px-4 text-[13px] font-medium text-text-secondary"
            >
              Refresh
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 border-t border-white/6 px-6 py-5 lg:grid-cols-4">
          <DashboardMetricCard
            label="Open approvals"
            value={String(approvalItems.length)}
            sub={`${attentionBuckets.needs_decision_now.length} high priority`}
            icon={BellRing}
            tone="indigo"
          />
          <DashboardMetricCard
            label="Active agents"
            value={String(agentStats?.active || 0)}
            sub={`${agentStats?.paused || 0} paused`}
            icon={Bot}
            tone="cyan"
          />
          <DashboardMetricCard
            label="Today's cost"
            value={financeStats ? formatCost(financeStats.todayCost) : '--'}
            sub={`${financeStats?.budgetUsedPct || 0}% of budget used`}
            icon={Coins}
            tone="green"
          />
          <DashboardMetricCard
            label="Hours saved"
            value={activityData ? `${activityData.hoursSavedToday ?? activityData.hoursSaved}h` : '--'}
            sub="Saved today by agents"
            icon={TimerReset}
            tone="amber"
          />
        </div>
      </section>

      {!loadingAttention && visibleSections.length === 0 ? (
        <DashboardEmptyState text="Nothing is waiting on you right now." />
      ) : (
        <div className="space-y-6">
          {(visibleSections.length ? visibleSections : URGENCY_SECTIONS).map((section) => {
            const items = attentionBuckets[section.key];
            return (
              <section key={section.key} className="space-y-3">
                <div className="flex items-end justify-between gap-3">
                  <div>
                    <h2 className="text-[1.5rem] font-semibold tracking-[-0.04em] text-text-primary lg:text-[1.7rem]">
                      {section.title}
                    </h2>
                  </div>
                  <span className="text-[13px] text-[#90a0be]">{items.length} items</span>
                </div>

                {loadingAttention ? (
                  <div className="space-y-4">
                    {[1, 2].map((i) => <SkeletonRow key={`${section.key}-${i}`} />)}
                  </div>
                ) : items.length === 0 ? null : (
                  <div className="space-y-4">
                    {items.map((item) => (
                      <TodayDecisionCard
                        key={item._id}
                        item={item}
                        onDismiss={handleDismiss}
                        onOpen={setSelectedApproval}
                      />
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}

      <ApprovalDrawer
        approval={selectedApproval}
        onClose={() => setSelectedApproval(null)}
        onRefresh={handleRefresh}
      />
    </DashboardPage>
  );
}

function buildAttentionItems(approvals, notifications) {
  const deduped = new Map();

  approvals.forEach((approval) => {
    deduped.set(approval._id, {
      ...approval,
      kind: 'approval',
      headline: approval.headline || approval.title || approval.subject || 'Pending decision',
      summary: pickBestSummary(approval),
      senderLine: approval.senderLine || approval.senderName || '',
      nextStepLine: approval.nextStepLine || '',
      kindLabel: approval.kindLabel || 'Action',
      sourceLabel: approval.agentName,
    });
  });

  notifications.forEach((notification) => {
    if (deduped.has(notification._id)) return;
    deduped.set(notification._id, {
      ...notification,
      kind: 'notification',
      headline: notification.title || notification.subject || notification.source || 'Alert',
      summary: notification.body,
      senderLine: '',
      nextStepLine: '',
      kindLabel: 'Alert',
      sourceLabel: notification.source,
      actions: [],
      isActionable: false,
      dueBucket: notification.dueBucket || 'today',
      urgencyLabel: notification.urgencyLabel || 'Worth handling today',
      urgencyScore: notification.urgencyScore || 0,
    });
  });

  return Array.from(deduped.values()).sort(compareDashboardItems);
}

function bucketAttentionItems(items) {
  return items.reduce((acc, item) => {
    const key = item.dueBucket || 'today';
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {
    needs_decision_now: [],
    today: [],
    can_wait: [],
  });
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

function SkeletonRow() {
  return (
    <div className="h-[160px] rounded-[22px] border border-white/6 bg-bg-card/70 animate-pulse" />
  );
}
