import { useState } from 'react';
import {
  X,
  Check,
  Loader2,
  PenSquare,
  Send,
  CalendarPlus,
  Trash2,
  Clock3,
  Sparkles,
  MessageSquareText,
  FileText,
  UserRound,
} from 'lucide-react';
import { useMutation } from '../../hooks/useApi.js';
import { timeAgo, detectTextDirection, pickBestHeadline, pickBestSummary, cn } from '../../lib/utils.js';
import AgentRichText from '../AgentRichText.jsx';

const ACTION_BUTTON_ICONS = {
  approve: Check,
  'approve-send': Send,
  'approve-calendar': CalendarPlus,
  'approve-draft': Check,
  'send-now': Send,
  'edit-draft': PenSquare,
  'execute-action': Check,
  'decline-politely': X,
  'defer-tomorrow': Clock3,
  'remind-tomorrow': Clock3,
  'review-tomorrow': Clock3,
  manual: PenSquare,
  cancel: X,
  'delete-message': Trash2,
};

const ACTION_BUTTON_STYLES = {
  primary: 'btn-primary h-10 w-full shadow-sm justify-center',
  secondary: 'btn-secondary h-10 w-full justify-center',
  ghost: 'btn-ghost h-10 w-full border border-border text-text-secondary hover:text-text-primary justify-center',
};

function ConfidencePill({ value }) {
  if (value == null) return null;
  const color = value >= 90
    ? 'text-[#c7d7ef] bg-[#90a0be]/12'
    : value >= 70
      ? 'text-[#e0bb83] bg-[#caa36d]/12'
      : 'text-[#c7d7ef] bg-[#75839b]/14';

  return (
    <span className={cn('text-[11px] font-semibold px-2.5 py-1 rounded-full', color)}>
      {value}% confidence
    </span>
  );
}

function Section({ icon: Icon, title, children, note }) {
  return (
    <section className="space-y-2.5">
      <div className="flex items-center gap-2 text-xs font-semibold text-text-muted uppercase tracking-wider">
        <Icon size={12} />
        <span>{title}</span>
      </div>
      {note && <p className="text-xs text-text-muted leading-relaxed">{note}</p>}
      {children}
    </section>
  );
}

function splitActions(actions) {
  const primary = [];
  const secondary = [];

  for (const action of actions) {
    if (action?.variant === 'primary' || action?.id === 'approve' || action?.id === 'approve-send') {
      primary.push(action);
    } else {
      secondary.push(action);
    }
  }

  return { primary, secondary };
}

function urgencyBadge(dueBucket) {
  if (dueBucket === 'needs_decision_now') {
    return 'bg-[#caa36d]/12 text-[#e0bb83] border border-[#caa36d]/20';
  }
  if (dueBucket === 'today') {
    return 'bg-[#90a0be]/12 text-[#c7d7ef] border border-[#90a0be]/18';
  }
  return 'bg-[#75839b]/12 text-[#b6c1d4] border border-[#75839b]/18';
}

export default function ApprovalDrawer({ approval, onClose, onRefresh }) {
  const [busy, setBusy] = useState(null);
  const [feedback, setFeedback] = useState('');
  const [showFeedback, setShowFeedback] = useState(false);
  const { mutate } = useMutation('patch', '/api/approvals');
  const { mutate: deleteApproval } = useMutation('delete', '/api/approvals');

  if (!approval) return null;

  const actions = Array.isArray(approval.actions) ? approval.actions : [];
  const footerActions = splitActions(actions);
  const headline = pickBestHeadline(approval);
  const summaryText = pickBestSummary(approval);
  const senderLine = approval.senderLine || approval.senderName || '';
  const nextStepLine = approval.nextStepLine || '';
  const outcomeLine = approval.outcomeLine || '';
  const sections = approval.previewSections || {};
  const contextLines = Array.isArray(sections.contextLines) ? sections.contextLines.filter(Boolean) : [];
  const filteredContextLines = contextLines.filter((line) => !String(line).startsWith('שולח:'));
  const draftTitle = sections.draftTitle || 'Proposed draft';
  const draftText = sections.draftText || approval.payload?.draft_preview || approval.content || '';
  const translationNote = sections.translationNote || '';
  const recommendation = sections.recommendation || outcomeLine;
  const subjectLine = approval.payload?.draft_subject || approval.payload?.subject || '';
  const headlineDir = detectTextDirection(headline, 'rtl');
  const senderDir = detectTextDirection(senderLine || approval.senderEmail || '', 'rtl');
  const draftDir = detectTextDirection(draftText, 'rtl');

  const handleAction = async (action) => {
    if (action.requiresInput) {
      setShowFeedback(true);
      return;
    }

    setBusy(action.id);
    try {
      if (action.callbackText) {
        await mutate({ callback_text: action.callbackText }, `/${approval._id}/callback`);
      } else {
        const suffix = action.id === 'approve' || action.id === 'reject'
          ? `/${approval._id}/${action.id}`
          : `/${approval._id}/action/${action.id}`;
        await mutate({}, suffix);
      }
      if (onRefresh) onRefresh();
      onClose();
    } finally {
      setBusy(null);
    }
  };

  const handleFeedbackSubmit = async () => {
    if (!feedback.trim()) return;
    setBusy('feedback');
    try {
      await mutate({ text: feedback }, `/${approval._id}/feedback`);
      if (onRefresh) onRefresh();
      onClose();
    } finally {
      setBusy(null);
    }
  };

  const handleTrash = async () => {
    setBusy('trash');
    try {
      await deleteApproval({}, `/${approval._id}`);
      if (onRefresh) onRefresh();
      onClose();
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-bg-primary/40 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-[34rem] h-full bg-bg-primary border-l border-border flex flex-col shadow-2xl animate-slide-left">
        <div className="h-[58px] flex items-center justify-between px-5 border-b border-border/60 bg-bg-secondary/30 flex-shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-semibold text-text-primary px-2.5 py-1 rounded-md bg-accent-indigo/10 text-accent-indigo">
              {approval.kindLabel || 'Action'}
            </span>
            <span className="text-[12px] text-text-muted">{timeAgo(approval.createdAt)}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleTrash}
              disabled={busy === 'trash'}
              className="p-2 rounded-lg hover:bg-[#caa36d]/10 text-text-muted hover:text-[#e0bb83] transition-colors"
              title="Remove from queue"
            >
              {busy === 'trash' ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
            </button>
            <div className="w-px h-4 bg-border mx-1" />
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-bg-hover text-text-muted" title="Close">
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
          <div className="space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={cn('text-[11px] font-semibold px-2.5 py-1 rounded-full', urgencyBadge(approval.dueBucket))}>
                {approval.urgencyLabel || 'Today'}
              </span>
              <ConfidencePill value={approval.confidence} />
              <span className="text-[12px] text-text-muted">{approval.agentName}</span>
            </div>

            <h2 className="text-[1.55rem] font-semibold text-text-primary leading-[1.2] break-words tracking-[-0.03em]" dir={headlineDir}>
              {headline}
            </h2>

            {senderLine && (
              <div className="flex items-start gap-3 rounded-xl border border-border/70 bg-bg-card px-4 py-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-indigo/10 text-accent-indigo">
                  <UserRound size={16} />
                </div>
                <div className="min-w-0">
                  <p className="text-[15px] font-medium text-text-primary break-words" dir={senderDir}>
                    {senderLine}
                  </p>
                  {approval.senderEmail && approval.senderEmail !== senderLine && (
                    <p className="text-[13px] text-text-muted break-all">{approval.senderEmail}</p>
                  )}
                </div>
              </div>
            )}
          </div>

          <Section icon={MessageSquareText} title="What arrived">
            <div className="rounded-xl border border-border bg-bg-secondary/80 px-4 py-3 space-y-3">
              {summaryText && (
                <AgentRichText
                  text={summaryText}
                  fallbackDirection={detectTextDirection(summaryText, 'rtl')}
                  blockClassName="text-sm text-text-primary"
                />
              )}
              {filteredContextLines.length > 0 && (
                <div className="space-y-1">
                  {filteredContextLines.map((line) => (
                    <p
                      key={line}
                      dir={detectTextDirection(line, 'rtl')}
                      className="text-xs text-text-muted leading-5"
                    >
                      {line}
                    </p>
                  ))}
                </div>
              )}
            </div>
          </Section>

          <Section icon={Sparkles} title="What the agent suggests">
            <div className="rounded-xl border border-border bg-bg-card px-4 py-4 space-y-3">
              {nextStepLine && (
                <div className="inline-flex items-center rounded-full border border-accent-indigo/20 bg-accent-indigo/10 px-2.5 py-1 text-[11px] font-semibold text-accent-indigo">
                  Suggested action: {nextStepLine}
                </div>
              )}
              {(outcomeLine || recommendation) && (
                <p dir={detectTextDirection(outcomeLine || recommendation, 'rtl')} className="text-sm text-text-primary leading-6">
                  {outcomeLine || recommendation}
                </p>
              )}
            </div>
          </Section>

          {draftText && (
            <Section icon={FileText} title={draftTitle} note={subjectLine ? `Subject: ${subjectLine}` : ''}>
              <div className="rounded-xl border border-border bg-bg-card px-4 py-4">
                <AgentRichText
                  text={draftText}
                  fallbackDirection={draftDir}
                  blockClassName="text-sm text-text-secondary leading-6"
                />
              </div>
            </Section>
          )}

          {translationNote && (
            <Section icon={MessageSquareText} title="Translation note">
              <div className="rounded-xl border border-border bg-bg-secondary/80 px-4 py-3">
                <p dir={detectTextDirection(translationNote, 'rtl')} className="text-sm text-text-muted leading-6">
                  {translationNote}
                </p>
              </div>
            </Section>
          )}

          <div className="h-1" />
        </div>

        <div className="p-4 bg-bg-primary border-t border-border flex-shrink-0 shadow-[0_-8px_30px_rgb(0,0,0,0.12)]">
          {showFeedback ? (
            <div className="space-y-3 animate-fade-in">
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                dir={detectTextDirection(feedback || draftText || summaryText, 'rtl')}
                className="w-full min-h-24 rounded-lg bg-bg-card border border-border px-3 py-3 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-indigo whitespace-pre-wrap resize-none"
                placeholder="Write clearer guidance for the agent..."
                autoFocus
              />
              <div className="flex gap-2">
                <button
                  onClick={() => setShowFeedback(false)}
                  disabled={busy === 'feedback'}
                  className="btn-ghost flex-1 h-10"
                >
                  Back
                </button>
                <button
                  onClick={handleFeedbackSubmit}
                  disabled={!feedback.trim() || busy === 'feedback'}
                  className="btn-primary flex-[2] h-10"
                >
                  {busy === 'feedback' ? <Loader2 size={16} className="animate-spin" /> : <Send size={14} />}
                  Send guidance
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {footerActions.primary.length > 0 && (
                <div className="grid gap-2">
                  {footerActions.primary.map((action) => {
                    const Icon = ACTION_BUTTON_ICONS[action.id] || Check;
                    return (
                      <button
                        key={action.id}
                        onClick={() => handleAction(action)}
                        disabled={!!busy}
                        className={ACTION_BUTTON_STYLES[action.variant] || ACTION_BUTTON_STYLES.primary}
                      >
                        {busy === action.id ? <Loader2 size={14} className="animate-spin" /> : <Icon size={14} />}
                        {action.label}
                      </button>
                    );
                  })}
                </div>
              )}

              {footerActions.secondary.length > 0 && (
                <div className={cn('grid gap-2', footerActions.primary.length > 0 ? 'grid-cols-2' : 'grid-cols-1')}>
                  {footerActions.secondary.map((action) => {
                    const Icon = ACTION_BUTTON_ICONS[action.id] || Check;
                    return (
                      <button
                        key={action.id}
                        onClick={() => handleAction(action)}
                        disabled={!!busy}
                        className={ACTION_BUTTON_STYLES[action.variant] || ACTION_BUTTON_STYLES.secondary}
                      >
                        {busy === action.id ? <Loader2 size={14} className="animate-spin" /> : <Icon size={14} />}
                        {action.label}
                      </button>
                    );
                  })}
                </div>
              )}

              {!footerActions.primary.length && !footerActions.secondary.length && (
                <div className="rounded-xl border border-border bg-bg-secondary/80 px-4 py-3 text-sm text-text-muted">
                  No HITL actions are currently available for this item.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
