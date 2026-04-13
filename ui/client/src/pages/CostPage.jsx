import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Clock3, Coins, DollarSign, PiggyBank, TrendingUp } from 'lucide-react';
import { format, subDays } from 'date-fns';
import { useApi } from '../hooks/useApi.js';
import { cn, formatCost } from '../lib/utils.js';
import {
  DashboardHero,
  DashboardMetricCard,
  DashboardPage,
  DashboardPanel,
} from '../components/chrome/DashboardPrimitives.jsx';

const PROVIDER_COLORS = {
  gemini: '#6366f1',
  anthropic: '#f59e0b',
  groq: '#10b981',
  aws: '#ef4444',
  mongodb: '#22d3ee',
};

export default function CostPage() {
  const { data: stats } = useApi('/api/finances/stats');
  const { data: finances } = useApi('/api/finances', { params: { days: 30 } });
  const { data: activity } = useApi('/api/activity', { params: { limit: 1 } });

  const chartData = (() => {
    const map = {};
    for (let i = 29; i >= 0; i -= 1) {
      const date = format(subDays(new Date(), i), 'MMM d');
      map[date] = { date, total: 0, gemini: 0, anthropic: 0, groq: 0, aws: 0 };
    }

    finances?.forEach((entry) => {
      const date = format(new Date(entry.date), 'MMM d');
      if (!map[date]) return;
      map[date].total += entry.amount;
      if (entry.provider && map[date][entry.provider] !== undefined) {
        map[date][entry.provider] += entry.amount;
      }
    });

    return Object.values(map);
  })();

  const providerTotals = (() => {
    const map = {};
    finances?.forEach((entry) => {
      const provider = entry.provider || 'other';
      map[provider] = (map[provider] || 0) + entry.amount;
    });
    return Object.entries(map).map(([name, cost]) => ({
      name,
      cost: Number(cost.toFixed(4)),
    }));
  })();

  const tooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="rounded-[16px] border border-white/8 bg-bg-card p-3 text-xs shadow-xl">
        <p className="mb-1.5 font-medium text-text-secondary">{label}</p>
        {payload.map((item) => (
          <div key={item.name} className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
            <span className="capitalize text-text-muted">{item.name}:</span>
            <span className="font-mono text-text-primary">{formatCost(item.value)}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <DashboardPage>
      <DashboardHero
        title="Cost & Value"
        meta={['Last 30 days', 'Operational spend and savings']}
        stats={[
          <DashboardMetricCard
            key="cost-today"
            label="Today's cost"
            value={stats ? formatCost(stats.todayCost) : '--'}
            sub="Current daily spend"
            icon={DollarSign}
            tone="indigo"
          />,
          <DashboardMetricCard
            key="cost-month"
            label="Monthly spend"
            value={stats ? formatCost(stats.monthCost) : '--'}
            sub="Accumulated this month"
            icon={Coins}
            tone="green"
          />,
          <DashboardMetricCard
            key="cost-budget"
            label="Budget used"
            value={stats ? `${stats.budgetUsedPct}%` : '--'}
            sub="Share of monthly budget"
            icon={PiggyBank}
            tone={(stats?.budgetUsedPct || 0) > 80 ? 'amber' : 'cyan'}
          />,
          <DashboardMetricCard
            key="cost-saved"
            label="Hours saved"
            value={activity ? `${activity.hoursSaved}h` : '--'}
            sub="Recovered by automation"
            icon={Clock3}
            tone="amber"
          />,
        ]}
      />

      <div className="grid gap-6 lg:grid-cols-[1.8fr_1fr]">
        <DashboardPanel className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-[1.2rem] font-semibold tracking-[-0.03em] text-text-primary">Daily spend</h2>
              <p className="mt-1 text-[13px] text-text-secondary">Per provider over the last 30 days</p>
            </div>
            <TrendingUp size={16} className="text-text-muted" />
          </div>

          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
              <defs>
                {Object.entries(PROVIDER_COLORS).map(([provider, color]) => (
                  <linearGradient key={provider} id={`grad-${provider}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={color} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2538" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fill: '#50586a', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value, index) => (index % 5 === 0 ? value : '')}
              />
              <YAxis
                tick={{ fill: '#50586a', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => `$${value.toFixed(2)}`}
                width={45}
              />
              <Tooltip content={tooltip} />
              {Object.entries(PROVIDER_COLORS).map(([provider, color]) => (
                <Area
                  key={provider}
                  type="monotone"
                  dataKey={provider}
                  stackId="1"
                  stroke={color}
                  fill={`url(#grad-${provider})`}
                  strokeWidth={1.5}
                  dot={false}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </DashboardPanel>

        <DashboardPanel className="p-5">
          <div className="mb-4">
            <h2 className="text-[1.2rem] font-semibold tracking-[-0.03em] text-text-primary">Budget</h2>
            <p className="mt-1 text-[13px] text-text-secondary">
              {stats ? formatCost(stats.monthCost) : '--'} / {formatCost(stats?.monthlyBudget || 50)}
            </p>
          </div>

          <div className="overflow-hidden rounded-full bg-bg-hover h-2.5">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-500',
                (stats?.budgetUsedPct || 0) > 80 ? 'bg-accent-amber' : 'bg-accent-green'
              )}
              style={{ width: `${Math.min(stats?.budgetUsedPct || 0, 100)}%` }}
            />
          </div>

          <p className="mt-3 text-[12px] text-text-secondary">
            {(stats?.budgetUsedPct || 0) > 80
              ? 'Approaching budget limit'
              : `${100 - (stats?.budgetUsedPct || 0)}% budget remaining`}
          </p>

          <div className="mt-6">
            <h3 className="mb-3 text-[12px] font-semibold uppercase tracking-[0.18em] text-[#7f8aa3]">
              Provider split
            </h3>
            <ResponsiveContainer width="100%" height={210}>
              <BarChart data={providerTotals} margin={{ top: 5, right: 10, bottom: 5, left: 0 }} barSize={28}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2538" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: '#50586a', fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis
                  tick={{ fill: '#50586a', fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value) => `$${value.toFixed(2)}`}
                  width={45}
                />
                <Tooltip content={tooltip} />
                <Bar
                  dataKey="cost"
                  radius={[6, 6, 0, 0]}
                  fill="#6366f1"
                  label={{ position: 'top', fill: '#50586a', fontSize: 9, formatter: (value) => `$${value.toFixed(2)}` }}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </DashboardPanel>
      </div>
    </DashboardPage>
  );
}
