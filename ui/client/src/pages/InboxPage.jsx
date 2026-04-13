import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useApi, useMutation } from '../hooks/useApi.js';
import {
  DASHBOARD_MODE,
  DASHBOARD_MODE_LABEL,
  IS_REAL_PREVIEW,
} from '../lib/apiClient.js';
import { timeAgo, cn, detectTextDirection } from '../lib/utils.js';
import AgentRichText from '../components/AgentRichText.jsx';
import {
  Mail,
  Filter,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Globe,
  Twitter,
  Linkedin,
  ArrowRight,
  Bell,
  Trash2,
} from 'lucide-react';

const SOURCE_ICONS = {
  gmail: { icon: Mail, color: 'text-accent-red', bg: 'bg-accent-red/10' },
  twitter: { icon: Twitter, color: 'text-accent-cyan', bg: 'bg-accent-cyan/10' },
  linkedin: { icon: Linkedin, color: 'text-accent-blue', bg: 'bg-accent-blue/10' },
  system: { icon: Globe, color: 'text-text-muted', bg: 'bg-bg-hover' },
};

const SENTIMENT_COLOR = {
  positive: 'text-accent-green bg-accent-green/10',
  neutral: 'text-text-muted bg-bg-hover',
  negative: 'text-accent-red bg-accent-red/10',
};

const PRIORITY_DOT = {
  high: 'bg-accent-red',
  medium: 'bg-accent-amber',
  low: 'bg-text-muted',
};

export default function InboxPage() {
  const [source, setSource] = useState('');
  const [expanded, setExpanded] = useState(null);
  const readOnlyPreview = IS_REAL_PREVIEW;
  const showModeBadge = DASHBOARD_MODE !== 'demo';

  const { data: items, loading, refresh } = useApi('/api/summaries', {
    params: source ? { source } : {},
  });
  const { mutate: markRead } = useMutation('patch', '/api/summaries');
  const { mutate: deleteSummary } = useMutation('delete', '/api/summaries');
  const [busy, setBusy] = useState(null);

  const summaryItems = Array.isArray(items) ? items : [];
  const actionableItems = summaryItems.filter((item) => item.isActionable);
  const contextItems = summaryItems.filter((item) => !item.isActionable);

  const handleExpand = async (id) => {
    if (expanded === id) {
      setExpanded(null);
      return;
    }
    setExpanded(id);
    if (readOnlyPreview) return;
    const item = summaryItems.find((entry) => entry._id === id);
    if (item && !item.read) {
      await markRead({}, `/${id}/read`);
      refresh();
    }
  };

  const handleDismiss = async (e, id) => {
    e.stopPropagation(); // prevent expanding
    if (readOnlyPreview) return;
    setBusy(id);
    try {
      await deleteSummary({}, `/${id}`);
      if (expanded === id) setExpanded(null);
      refresh();
    } finally {
      setBusy(null);
    }
  };

  const sources = ['', 'gmail', 'linkedin', 'twitter', 'system'];

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold text-text-primary">Email Inbox</h1>
            {showModeBadge && (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-accent-amber/10 text-accent-amber border border-accent-amber/20">
                {DASHBOARD_MODE_LABEL}
              </span>
            )}
          </div>
          <p className="text-sm text-text-muted mt-0.5">Summaries, signals, and context. Actionable HITL items live in Approvals.</p>
        </div>
        <button onClick={refresh} className="btn-ghost">
          <RefreshCw size={13} className={cn(loading && 'animate-spin')} /> Refresh
        </button>
      </div>

      {actionableItems.length > 0 && (
        <div className="card border border-accent-indigo/20 bg-accent-indigo/5 p-4 flex items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-xl bg-accent-indigo/10 flex items-center justify-center flex-shrink-0">
              <Bell size={14} className="text-accent-indigo" />
            </div>
            <div>
              <p className="text-sm font-medium text-text-primary">
                {actionableItems.length} active HITL items pending in Approvals
              </p>
              <p className="text-xs text-text-muted mt-1">
                Active approvals are not shown here as action cards to keep the decision queue clear.
              </p>
            </div>
          </div>
          <Link to="/approvals" className="btn-secondary h-9 text-[11px] gap-1 whitespace-nowrap">
            Go to Approvals <ArrowRight size={12} />
          </Link>
        </div>
      )}

      <div className="flex items-center gap-1.5 flex-wrap">
        <Filter size={12} className="text-text-muted mr-1" />
        {sources.map((itemSource) => (
          <button
            key={itemSource || 'all'}
            onClick={() => setSource(itemSource)}
            className={cn(
              'px-3 py-1 rounded-full text-xs font-medium transition-all',
              source === itemSource
                ? 'bg-accent-indigo text-white'
                : 'bg-bg-hover text-text-secondary hover:text-text-primary border border-border'
            )}
          >
            {itemSource || 'All Sources'}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => <div key={i} className="card p-4 animate-pulse h-16" />)}
        </div>
      ) : !contextItems.length ? (
        <div className="card p-10 text-center">
          <Mail size={24} className="text-text-muted mx-auto mb-2" />
          <p className="text-text-muted text-sm">
            {actionableItems.length > 0
              ? 'No context summaries at the moment. Active approvals are available in the Approvals queue.'
              : 'No insights yet. This page shows summaries and context from processed emails.'}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {contextItems.map((item) => {
            const src = SOURCE_ICONS[item.source] || SOURCE_ICONS.system;
            const SrcIcon = src.icon;
            const isOpen = expanded === item._id;
            return (
              <div
                key={item._id}
                className={cn('card transition-all duration-200 group', !item.read && 'border-border-light', isOpen && 'glow-indigo')}
              >
                <button
                  className="w-full p-4 flex items-start gap-3 text-left"
                  onClick={() => handleExpand(item._id)}
                >
                  <div className={cn('w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5', src.bg)}>
                    <SrcIcon size={13} className={src.color} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      {!item.read && <div className="w-1.5 h-1.5 rounded-full bg-accent-indigo flex-shrink-0" />}
                      <p className={cn('text-sm leading-snug', !item.read ? 'font-semibold text-text-primary' : 'font-medium text-text-secondary')}>
                        {item.title}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <div className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', PRIORITY_DOT[item.priority])} />
                      <span className="text-[10px] text-text-muted capitalize">{item.priority} priority</span>
                      <span className="text-text-muted text-[10px]">·</span>
                      <span className="text-[10px] text-text-muted">{timeAgo(item.createdAt)}</span>
                      <span className="text-text-muted text-[10px]">·</span>
                      <span className="text-[10px] text-text-muted">{item.agentName}</span>
                      <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded-full capitalize', SENTIMENT_COLOR[item.sentiment])}>
                        {item.sentiment}
                      </span>
                    </div>
                  </div>
                  <div className="flex-shrink-0 flex items-center gap-2 mt-1">
                    <button
                      onClick={(e) => handleDismiss(e, item._id)}
                      disabled={readOnlyPreview || busy === item._id}
                      className="p-1 rounded-lg hover:bg-accent-red/10 transition-colors opacity-0 group-hover:opacity-100 flex-shrink-0"
                      title="Dismiss insight"
                    >
                      {busy === item._id ? <RefreshCw size={14} className="animate-spin text-text-muted" /> : <Trash2 size={14} className="text-text-muted hover:text-accent-red transition-colors" />}
                    </button>
                    <span className="text-text-muted">
                      {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </span>
                  </div>
                </button>
                {isOpen && (
                  <div className="px-4 pb-4 animate-slide-up">
                    <div className="pt-3 border-t border-border">
                      <AgentRichText
                        text={item.content}
                        fallbackDirection={detectTextDirection(item.content, 'rtl')}
                        blockClassName="text-sm text-text-secondary"
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
