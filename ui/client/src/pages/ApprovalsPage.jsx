import { useState } from 'react';
import { Bell } from 'lucide-react';
import { useApi, useMutation } from '../hooks/useApi.js';
import ApprovalDrawer from '../components/Approvals/ApprovalDrawer.jsx';
import DecisionSummaryCard from '../components/Approvals/DecisionSummaryCard.jsx';

const STATUS_LABELS = {
  pending: 'Pending',
  approved: 'Approved',
  rejected: 'Rejected',
};

const compareDashboardItems = (left, right) => {
  const actionableDelta = Number(Boolean(right?.isActionable)) - Number(Boolean(left?.isActionable));
  if (actionableDelta !== 0) return actionableDelta;

  const freshDelta = Number((right?.freshnessBoost || 0) > 0) - Number((left?.freshnessBoost || 0) > 0);
  if (freshDelta !== 0) return freshDelta;

  const createdDelta = String(right?.createdAt || '').localeCompare(String(left?.createdAt || ''));
  if (createdDelta !== 0) return createdDelta;

  return Number(right?.sortRank || right?.urgencyScore || 0) - Number(left?.sortRank || left?.urgencyScore || 0);
};

export default function ApprovalsPage() {
  const [filter, setFilter] = useState('pending');
  const [selectedApproval, setSelectedApproval] = useState(null);
  const { data, loading, refresh } = useApi('/api/approvals', { params: { status: filter } });
  const { mutate: dismissApproval } = useMutation('delete', '/api/approvals');
  const approvals = [...(Array.isArray(data) ? data : [])].sort(compareDashboardItems);

  const handleDismiss = async (item) => {
    if (!item?._id) return;
    await dismissApproval({}, `/${item._id}`);
    refresh();
  };

  return (
    <div className="mx-auto w-full max-w-[1120px] space-y-6 animate-fade-in">
      <section className="overflow-hidden rounded-[28px] border border-white/6 bg-[linear-gradient(180deg,rgba(17,22,34,0.92),rgba(10,14,22,0.98))] shadow-[0_18px_60px_rgba(0,0,0,0.32)]">
        <div className="flex flex-col gap-5 px-6 py-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-[2.45rem] font-semibold leading-none tracking-[-0.05em] text-text-primary">
              Approvals
            </h1>
            <div className="mt-3 text-[13px] text-[#90a0be]">
              {approvals.length} items in {STATUS_LABELS[filter].toLowerCase()}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {['pending', 'approved', 'rejected'].map((status) => (
              <button
                key={status}
                onClick={() => setFilter(status)}
                className={[
                  'inline-flex min-h-[34px] items-center rounded-full border px-4 text-[13px] font-semibold transition-colors',
                  filter === status
                    ? 'border-[#7884ff]/20 bg-[#7884ff]/14 text-[#d4daff]'
                    : 'border-white/7 bg-white/[0.03] text-text-secondary hover:text-text-primary',
                ].join(' ')}
              >
                {STATUS_LABELS[status]}
              </button>
            ))}
          </div>
        </div>

        <div className="px-6 pb-6">
          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-[160px] rounded-[22px] border border-white/6 bg-bg-card/70 animate-pulse" />
              ))}
            </div>
          ) : !approvals.length ? (
            <div className="rounded-[24px] border border-white/6 bg-bg-card/80 p-12 text-center">
              <Bell size={24} className="mx-auto mb-3 text-text-muted" />
              <p className="text-sm text-text-muted">
                No items are currently in {STATUS_LABELS[filter].toLowerCase()}.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {approvals.map((approval) => (
                <DecisionSummaryCard
                  key={approval._id}
                  item={approval}
                  onOpen={setSelectedApproval}
                  onDismiss={handleDismiss}
                />
              ))}
            </div>
          )}
        </div>
      </section>

      <ApprovalDrawer
        approval={selectedApproval}
        onClose={() => setSelectedApproval(null)}
        onRefresh={refresh}
      />
    </div>
  );
}
