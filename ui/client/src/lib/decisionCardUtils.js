import { pickBestHeadline, timeAgo } from './utils.js';

export const DECISION_TONE = {
  needs_decision_now: {
    accent: 'bg-[#caa36d]',
    importancePill: 'bg-[#caa36d]/10 text-[#e3c08b] border border-[#caa36d]/20',
  },
  today: {
    accent: 'bg-[#9aa8c7]',
    importancePill: 'bg-[#90a0be]/12 text-[#c8d4eb] border border-[#90a0be]/16',
  },
  can_wait: {
    accent: 'bg-[#75839b]',
    importancePill: 'bg-[#6f7c95]/12 text-[#b2bdd1] border border-[#6f7c95]/18',
  },
};

const DUE_BUCKET_LABELS = {
  needs_decision_now: {
    pill: 'High priority',
    fact: 'Needs decision now',
  },
  today: {
    pill: 'Today',
    fact: 'Worth handling today',
  },
  can_wait: {
    pill: 'Can wait',
    fact: 'Can stay in queue',
  },
};

const FALLBACK_TONE = DECISION_TONE.today;
const FALLBACK_LABELS = DUE_BUCKET_LABELS.today;

const DECISION_TYPE_LABELS = {
  incoming_email: 'Reply decision',
  send_email: 'Reply decision',
  create_draft: 'Reply decision',
  create_event: 'Meeting action',
  update_event_time: 'Meeting action',
  delete_event: 'Meeting action',
  multi_step: 'Decision',
};

function compactWhitespace(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

export function shortenSenderName(value) {
  let normalized = compactWhitespace(value);
  if (!normalized) return '';

  normalized = normalized
    .replace(/^from\s+/i, '')
    .split('|')[0]
    .replace(/\([^)]*@[^)]*\)/g, '')
    .replace(/<[^>]*@[^>]*>/g, '')
    .replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, '')
    .trim();

  if (!normalized) return '';

  const tokens = normalized
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);

  if (tokens.length <= 2) return tokens.join(' ');
  return tokens.slice(0, 2).join(' ');
}

function buildTypeLabel(item, decision) {
  const subjectSource = `${decision?.subjectSummary || ''} ${pickBestHeadline(item, '')}`.toLowerCase();

  if (item?.kind === 'notification') return 'Alert';

  if (decision?.isMeeting) {
    return item?.actionType === 'create_event' || item?.actionType === 'update_event_time'
      ? 'Meeting action'
      : 'Meeting reply';
  }

  if (/\bbilling\b|\binvoice\b|\bpayment\b|\bcost\b|\breceipt\b|\bcharge\b/.test(subjectSource)) {
    return 'Finance alert';
  }

  return DECISION_TYPE_LABELS[item?.actionType] || item?.kindLabel || 'Decision';
}

export function buildDecisionCardModel(item) {
  const decision = item?.decisionData || {};
  const dueBucket = item?.dueBucket || 'today';
  const labels = DUE_BUCKET_LABELS[dueBucket] || FALLBACK_LABELS;
  const tone = DECISION_TONE[dueBucket] || FALLBACK_TONE;
  const confidence = typeof item?.confidence === 'number'
    ? item.confidence
    : (typeof decision?.confidence === 'number' ? decision.confidence : null);
  const entered = timeAgo(item?.createdAt);
  const sender = decision?.senderShortName
    || shortenSenderName(item?.senderLine || item?.senderName || item?.sourceLabel || item?.senderEmail || item?.title)
    || 'Unknown sender';
  const subject = compactWhitespace(
    decision?.subjectSummary
    || pickBestHeadline(item, item?.kind === 'notification' ? 'Notification' : 'Pending decision')
  );

  return {
    dueBucket,
    tone,
    importancePill: labels.pill,
    importanceFact: labels.fact,
    typeLabel: buildTypeLabel(item, decision),
    enteredLabel: entered ? `Arrived ${entered}` : 'Arrived recently',
    enteredFact: entered || 'Recently',
    confidence,
    confidencePill: confidence == null ? null : `Confidence ${confidence}%`,
    confidenceFact: confidence == null ? 'Review required' : `Agent confidence ${confidence}%`,
    sender,
    subject,
  };
}
