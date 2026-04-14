import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { formatDistanceToNow, format } from 'date-fns';

export function cn(...inputs) { return twMerge(clsx(inputs)); }

export function timeAgo(date) {
  if (!date) return '';
  return formatDistanceToNow(new Date(date), { addSuffix: true });
}

export function formatDate(date, fmt = 'MMM d, yyyy') {
  if (!date) return '';
  return format(new Date(date), fmt);
}

export function formatCost(usd) {
  if (usd < 0.01) return `$${(usd).toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

export function formatNumber(n, dec = 1) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return Number.isInteger(n) ? String(n) : n.toFixed(dec);
}

export const SEVERITY_COLORS = {
  low:      { dot: 'bg-accent-green',  badge: 'bg-accent-green/10  text-accent-green',  label: 'Low'      },
  medium:   { dot: 'bg-accent-amber',  badge: 'bg-accent-amber/10  text-accent-amber',  label: 'Medium'   },
  high:     { dot: 'bg-accent-red',    badge: 'bg-accent-red/10    text-accent-red',    label: 'High'     },
  critical: { dot: 'bg-red-600',       badge: 'bg-red-600/10       text-red-400',       label: 'Critical' },
};

export const STATUS_COLORS = {
  active:  'text-accent-green',
  idle:    'text-text-muted',
  paused:  'text-accent-amber',
  error:   'text-accent-red',
  success: 'text-accent-green',
  pending: 'text-accent-amber',
  failed:  'text-accent-red',
  approved:'text-accent-blue',
  rejected:'text-text-muted',
};

export const AGENT_COLORS = {
  SecretariatAgent: '#6366f1',
  FinanceAgent:     '#10b981',
  KnowledgeAgent:   '#8b5cf6',
  WebSearchAgent:   '#f59e0b',
  system:           '#94a3b8',
};

const RTL_CHAR_RE = /[\u0590-\u05FF\u0600-\u06FF]/;
const LTR_CHAR_RE = /[A-Za-z]/;

export function detectTextDirection(text, fallback = 'rtl') {
  const value = String(text || '');
  for (const char of value) {
    if (RTL_CHAR_RE.test(char)) return 'rtl';
    if (LTR_CHAR_RE.test(char)) return 'ltr';
  }
  return fallback;
}

export function getDirectionalTextClass(textOrDirection, fallback = 'rtl') {
  const direction = textOrDirection === 'rtl' || textOrDirection === 'ltr'
    ? textOrDirection
    : detectTextDirection(textOrDirection, fallback);

  return direction === 'rtl' ? 'text-right' : 'text-left';
}

export function getDirectionalTextProps(text, fallback = 'rtl') {
  const dir = detectTextDirection(text, fallback);
  return {
    dir,
    textAlignClass: getDirectionalTextClass(dir),
  };
}

export function splitTextBlocks(text) {
  return String(text || '')
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);
}

const BUTTON_MARKER_RE = /\[\[BUTTONS:\s*([\s\S]+?)\s*\]\]/i;

export function parseButtonMarker(text) {
  const value = String(text || '');
  const match = value.match(BUTTON_MARKER_RE);
  if (!match) {
    return { text: value, buttons: [] };
  }

  const rawButtons = match[1]
    .trim()
    .replace(/^\[/, '')
    .replace(/\]$/, '')
    .replace(/['"]/g, '');

  const buttonCandidates = rawButtons.includes('|')
    ? rawButtons.split('|')
    : rawButtons.includes(',')
      ? rawButtons.split(',')
      : [rawButtons];

  const seen = new Set();
  const buttons = buttonCandidates
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => {
      const key = item.replace(/\s+/g, ' ').trim().toLowerCase();
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });

  return {
    text: value.replace(BUTTON_MARKER_RE, '').trim(),
    buttons,
  };
}

export function stripButtonMarker(text) {
  return parseButtonMarker(text).text;
}

export function isLowSignalHeadline(text) {
  const normalized = String(text || '').trim().toLowerCase();
  if (!normalized) return true;
  return [
    'פגישה',
    'מייל',
    'טיוטה',
    'email',
    'draft',
    'reply',
    'reply needed',
    'incoming email',
    'message',
  ].includes(normalized);
}

export function pickBestHeadline(item, fallback = 'Untitled') {
  const contextLines = Array.isArray(item?.previewSections?.contextLines)
    ? item.previewSections.contextLines
    : [];
  const candidates = [
    item?.headline,
    item?.payload?.event_title,
    item?.payload?.draft_subject,
    item?.payload?.subject,
    contextLines[0],
    item?.summaryLine,
    item?.summary,
    item?.title,
  ];

  let selected = '';
  for (const candidate of candidates) {
    const value = String(candidate || '').trim();
    if (!value) continue;
    if (!isLowSignalHeadline(value)) return value;
    if (!selected) selected = value;
  }

  return selected || fallback;
}

export function pickBestSummary(item, fallback = '') {
  const headline = pickBestHeadline(item, '');
  const contextLines = Array.isArray(item?.previewSections?.contextLines)
    ? item.previewSections.contextLines
    : [];
  const candidates = [
    item?.summaryLine,
    item?.summary,
    item?.payload?.summary,
    contextLines.find((line) => !String(line || '').startsWith('שולח:') && !String(line || '').startsWith('מועד')),
    item?.description,
    item?.body,
  ];

  let selected = '';
  for (const candidate of candidates) {
    const value = String(candidate || '').trim();
    if (!value) continue;
    if (value === headline) {
      if (!selected) selected = value;
      continue;
    }
    if (!isLowSignalHeadline(value)) return value;
    if (!selected) selected = value;
  }

  return selected || fallback;
}
