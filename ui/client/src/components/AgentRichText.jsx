import { cn, detectTextDirection, splitTextBlocks, stripButtonMarker } from '../lib/utils.js';

const BULLET_RE = /^[-*•]\s+(.+)$/;

function renderInlineSegments(text, keyPrefix) {
  const value = String(text || '');
  const parts = [];
  const boldRe = /\*\*([^*]+)\*\*/g;
  let lastIndex = 0;
  let match;

  while ((match = boldRe.exec(value)) !== null) {
    if (match.index > lastIndex) {
      parts.push(
        <span key={`${keyPrefix}-plain-${lastIndex}`}>
          {value.slice(lastIndex, match.index)}
        </span>
      );
    }

    parts.push(
      <strong key={`${keyPrefix}-bold-${match.index}`} className="font-semibold">
        {match[1]}
      </strong>
    );

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < value.length) {
    parts.push(
      <span key={`${keyPrefix}-plain-tail`}>
        {value.slice(lastIndex)}
      </span>
    );
  }

  return parts.length ? parts : value;
}

function parseStructuredLine(line) {
  const trimmed = String(line || '').trim();
  if (!trimmed) return { type: 'empty', value: '' };

  const bulletMatch = trimmed.match(BULLET_RE);
  if (bulletMatch) {
    return { type: 'bullet', value: bulletMatch[1].trim() };
  }

  const colonIndex = trimmed.indexOf(':');
  if (colonIndex > 0) {
    const rawLabel = trimmed.slice(0, colonIndex).trim();
    const value = trimmed.slice(colonIndex + 1).trim();
    const normalizedLabel = rawLabel.replace(/^[^A-Za-z0-9\u0590-\u05FF]+/u, '').trim();
    const wordCount = normalizedLabel.split(/\s+/).filter(Boolean).length;

    if (normalizedLabel && value && normalizedLabel.length <= 24 && wordCount <= 4) {
      return {
        type: 'field',
        label: rawLabel,
        value,
      };
    }
  }

  return { type: 'paragraph', value: trimmed };
}

function renderBlock(block, direction, keyPrefix, blockClassName) {
  const lines = String(block || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

  const parsedLines = lines.map(parseStructuredLine).filter((line) => line.type !== 'empty');

  if (!parsedLines.length) return null;

  const allBullets = parsedLines.every((line) => line.type === 'bullet');

  if (allBullets) {
    return (
      <ul key={`${keyPrefix}-bullets`} className="space-y-2">
        {parsedLines.map((line, index) => {
          const itemDirection = detectTextDirection(line.value, direction);
          return (
            <li
              key={`${keyPrefix}-bullet-${index}`}
              dir={itemDirection}
              style={{ unicodeBidi: 'plaintext' }}
              className={cn(
                'flex gap-2 whitespace-pre-wrap break-words text-[12px] leading-6',
                itemDirection === 'rtl' ? 'flex-row-reverse text-right' : 'text-left',
                blockClassName
              )}
            >
              <span className="mt-[0.55rem] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-accent-indigo/70" />
              <span>{renderInlineSegments(line.value, `${keyPrefix}-bullet-content-${index}`)}</span>
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <div key={`${keyPrefix}-mixed`} className="space-y-2.5">
      {parsedLines.map((line, index) => {
        if (line.type === 'field') {
          const valueDirection = detectTextDirection(line.value, direction);
          return (
            <div
              key={`${keyPrefix}-field-${index}`}
              dir={valueDirection}
              style={{ unicodeBidi: 'plaintext' }}
              className={cn(
                'rounded-[16px] border border-white/6 bg-white/[0.025] px-3 py-2.5',
                valueDirection === 'rtl' ? 'text-right' : 'text-left'
              )}
            >
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
                {line.label}
              </div>
              <div className={cn('text-[12px] leading-6 text-text-primary', blockClassName)}>
                {renderInlineSegments(line.value, `${keyPrefix}-field-content-${index}`)}
              </div>
            </div>
          );
        }

        const lineDirection = detectTextDirection(line.value, direction);
        return (
          <p
            key={`${keyPrefix}-paragraph-${index}`}
            dir={lineDirection}
            style={{ unicodeBidi: 'plaintext' }}
            className={cn(
              'whitespace-pre-wrap break-words text-[12px] leading-6',
              lineDirection === 'rtl' ? 'text-right' : 'text-left',
              blockClassName
            )}
          >
            {renderInlineSegments(line.value, `${keyPrefix}-paragraph-content-${index}`)}
          </p>
        );
      })}
    </div>
  );
}

export default function AgentRichText({
  text,
  className = '',
  blockClassName = '',
  fallbackDirection = 'rtl',
}) {
  const safeText = stripButtonMarker(text);
  const blocks = splitTextBlocks(safeText);
  const direction = detectTextDirection(safeText, fallbackDirection);

  if (!blocks.length) return null;

  return (
    <div
      dir={direction}
      className={cn(
        'space-y-3',
        direction === 'rtl' ? 'text-right' : 'text-left',
        className
      )}
    >
      {blocks.map((block, index) => renderBlock(block, direction, `${index}-${block.slice(0, 20)}`, blockClassName))}
    </div>
  );
}
