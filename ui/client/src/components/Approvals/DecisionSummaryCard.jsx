import { ChevronRight, Trash2 } from 'lucide-react';
import { buildDecisionCardModel } from '../../lib/decisionCardUtils.js';
import { cn, detectTextDirection } from '../../lib/utils.js';

function MetaPill({ children, className }) {
  return (
    <span
      className={cn(
        'inline-flex min-h-[28px] items-center rounded-full border border-white/8 bg-white/[0.03] px-3 text-[11px] font-semibold text-text-secondary',
        className
      )}
    >
      {children}
    </span>
  );
}

function FactBox({ label, value, dir, className }) {
  return (
    <div className={cn('rounded-[15px] border border-white/7 bg-white/[0.025] px-3.5 py-3', className)}>
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#7f8aa3]">
        {label}
      </div>
      <div className="text-[13px] font-semibold leading-[1.45] text-text-primary" dir={dir}>
        {value}
      </div>
    </div>
  );
}

export default function DecisionSummaryCard({
  item,
  onOpen,
  onDismiss,
  notificationsReadOnly = false,
}) {
  const isApproval = item?.kind !== 'notification';
  const model = buildDecisionCardModel(item);
  const subjectDir = detectTextDirection(model.subject, 'rtl');
  const senderDir = detectTextDirection(model.sender, subjectDir);
  const canDismiss = typeof onDismiss === 'function';

  return (
    <article className="relative overflow-hidden rounded-[22px] border border-white/6 bg-[linear-gradient(180deg,rgba(21,28,43,0.98),rgba(16,21,34,0.98))] px-4 py-4 shadow-[0_18px_45px_rgba(0,0,0,0.24)] lg:px-5">
      <div className={cn('absolute bottom-4 left-0 top-4 w-[3px] rounded-full', model.tone.accent)} />

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap gap-2">
            <MetaPill className={model.tone.importancePill}>{model.importancePill}</MetaPill>
            <MetaPill>{model.typeLabel}</MetaPill>
            <MetaPill>{model.enteredLabel}</MetaPill>
            {model.confidencePill && <MetaPill className="border-[#7884ff]/20 bg-[#7884ff]/12 text-[#c5ceff]">{model.confidencePill}</MetaPill>}
          </div>

          <h3
            className="mt-4 max-w-[44rem] text-[clamp(1.22rem,1.2vw,1.55rem)] font-semibold leading-[1.18] tracking-[-0.04em] text-text-primary"
            dir={subjectDir}
          >
            {model.subject}
          </h3>

          <div className="mt-4 grid grid-cols-2 gap-2.5 lg:grid-cols-4">
            <FactBox label="From" value={model.sender} dir={senderDir} />
            <FactBox label="Importance" value={model.importanceFact} dir={detectTextDirection(model.importanceFact, 'ltr')} className="text-text-secondary" />
            <FactBox label="Entered" value={model.enteredFact} dir="ltr" className="text-text-secondary" />
            <FactBox label="Confidence" value={model.confidenceFact} dir="ltr" className="text-text-secondary" />
          </div>
        </div>

        <div className="flex items-start justify-start gap-2 lg:justify-end lg:pl-3">
          {isApproval ? (
            <>
              {canDismiss && (
                <button
                  onClick={() => onDismiss?.(item)}
                  className="inline-flex h-[42px] w-[42px] items-center justify-center rounded-[14px] border border-white/8 bg-white/[0.03] text-text-secondary transition-colors duration-150 hover:text-text-primary"
                  title="Dismiss"
                >
                  <Trash2 size={15} />
                </button>
              )}
              <button
                onClick={() => onOpen?.(item)}
                className="inline-flex min-h-[42px] items-center justify-center gap-2 rounded-[14px] border border-[#7884ff]/20 bg-gradient-to-b from-[#6f7cff] to-[#6672ea] px-4.5 text-[14px] font-semibold text-white shadow-[0_10px_28px_rgba(102,114,234,0.2)] transition-transform duration-150 hover:-translate-y-[1px]"
              >
                Open decision
                <ChevronRight size={16} />
              </button>
            </>
          ) : (
            <button
              onClick={() => onDismiss?.(item)}
              disabled={notificationsReadOnly}
              className="inline-flex h-[42px] w-[42px] items-center justify-center rounded-[14px] border border-white/8 bg-white/[0.03] text-text-secondary transition-colors duration-150 hover:text-text-primary disabled:opacity-40"
              title="Dismiss"
            >
              <Trash2 size={15} />
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
