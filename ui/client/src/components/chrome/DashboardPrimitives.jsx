import { Clock3 } from 'lucide-react';
import { cn } from '../../lib/utils.js';

const TONE_MAP = {
  indigo: {
    wrapper: 'bg-accent-indigo/10 border-accent-indigo/16',
    icon: 'text-accent-indigo',
  },
  cyan: {
    wrapper: 'bg-accent-cyan/10 border-accent-cyan/16',
    icon: 'text-accent-cyan',
  },
  green: {
    wrapper: 'bg-accent-green/10 border-accent-green/16',
    icon: 'text-accent-green',
  },
  amber: {
    wrapper: 'bg-accent-amber/10 border-accent-amber/16',
    icon: 'text-accent-amber',
  },
  red: {
    wrapper: 'bg-accent-red/10 border-accent-red/16',
    icon: 'text-accent-red',
  },
};

export function DashboardPage({ children }) {
  return <div className="mx-auto w-full max-w-[1120px] space-y-6 animate-fade-in">{children}</div>;
}

export function DashboardHero({
  title,
  eyebrow,
  meta = [],
  actions = null,
  stats = null,
  children = null,
}) {
  return (
    <section className="overflow-hidden rounded-[28px] border border-white/6 bg-[linear-gradient(180deg,rgba(17,22,34,0.92),rgba(10,14,22,0.98))] shadow-[0_18px_60px_rgba(0,0,0,0.32)]">
      <div className="flex flex-col gap-5 px-6 py-6 lg:flex-row lg:items-start lg:justify-between">
        <div>
          {eyebrow ? (
            <div className="mb-2 text-[12px] font-medium uppercase tracking-[0.18em] text-[#7f8aa3]">
              {eyebrow}
            </div>
          ) : null}
          <h1 className="text-[2.45rem] font-semibold leading-none tracking-[-0.05em] text-text-primary">
            {title}
          </h1>
          {meta?.length ? (
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px] text-[#90a0be]">
              {meta.map((item, index) => (
                <span key={`${title}-meta-${index}`}>{item}</span>
              ))}
            </div>
          ) : null}
          {children}
        </div>

        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>

      {stats ? (
        <div className="grid grid-cols-2 gap-3 border-t border-white/6 px-6 py-5 lg:grid-cols-4">
          {stats}
        </div>
      ) : null}
    </section>
  );
}

export function DashboardMetricCard({ label, value, sub, icon: Icon, tone = 'indigo' }) {
  const palette = TONE_MAP[tone] || TONE_MAP.indigo;

  return (
    <div className="min-h-[106px] rounded-[20px] border border-white/6 bg-white/[0.01] px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7f8aa3]">
          {label}
        </div>
        {Icon ? (
          <div className={cn('flex h-9 w-9 items-center justify-center rounded-[14px] border', palette.wrapper)}>
            <Icon size={15} className={palette.icon} />
          </div>
        ) : null}
      </div>
      <div className="mt-3 text-[2.15rem] font-semibold leading-none tracking-[-0.06em] text-text-primary">
        {value}
      </div>
      <div className="mt-2 text-[13px] leading-5 text-text-secondary">
        {sub}
      </div>
    </div>
  );
}

export function DashboardEmptyState({
  icon: Icon = Clock3,
  title = '',
  text,
  className = '',
}) {
  return (
    <div className={cn('rounded-[24px] border border-white/6 bg-bg-card/80 p-10 text-center', className)}>
      <Icon size={22} className="mx-auto mb-3 text-text-muted" />
      {title ? <p className="text-sm font-medium text-text-primary">{title}</p> : null}
      <p className={cn('text-sm text-text-muted', title ? 'mt-1.5' : '')}>{text}</p>
    </div>
  );
}

export function DashboardPanel({ className = '', children }) {
  return (
    <section className={cn('rounded-[24px] border border-white/6 bg-bg-card/80 p-5 shadow-[0_12px_40px_rgba(0,0,0,0.18)]', className)}>
      {children}
    </section>
  );
}
