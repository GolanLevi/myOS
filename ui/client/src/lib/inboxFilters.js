const SUPPRESSED_PREVIEW_MARKERS = [
  '[ignore_email]',
  'low-value-notification',
  'empty-email',
];

export function isSuppressedInboxItem(item) {
  if (!item || typeof item !== 'object') return false;

  const status = String(item.status || '').trim().toLowerCase();
  if (['ignored', 'dismissed', 'expired'].includes(status)) {
    return true;
  }

  const priority = String(item.priority || '').trim().toLowerCase();
  if (priority === 'low') {
    return true;
  }

  const searchableText = [
    item.title,
    item.summary,
    item.content,
    item.senderName,
    item.senderEmail,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  return SUPPRESSED_PREVIEW_MARKERS.some((marker) => searchableText.includes(marker));
}

export function getVisibleInboxItems(items) {
  if (!Array.isArray(items)) return [];
  return items.filter((item) => !isSuppressedInboxItem(item));
}
