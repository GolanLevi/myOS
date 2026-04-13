import { useState, useEffect, useRef, useCallback } from 'react';
import { apiGet, apiPost, apiDelete } from '../../lib/apiClient.js';
import { useApi } from '../../hooks/useApi.js';
import {
  timeAgo,
  cn,
  detectTextDirection,
  parseButtonMarker,
  stripButtonMarker,
} from '../../lib/utils.js';
import AgentRichText from '../AgentRichText.jsx';
import {
  Bot,
  CalendarDays,
  Check,
  ChevronLeft,
  FileText,
  Loader2,
  Mail,
  Pencil,
  Plus,
  Search,
  Send,
  Sparkles,
  Trash2,
  User,
} from 'lucide-react';

function includesAny(value, needles) {
  const normalized = String(value || '').toLowerCase();
  return needles.some((needle) => normalized.includes(needle));
}

function getTopicVisual(...parts) {
  const sample = parts.filter(Boolean).join(' ');

  if (includesAny(sample, ['פגישה', 'meeting', 'calendar', 'event', 'schedule'])) {
    return {
      Icon: CalendarDays,
      ringClass: 'bg-accent-amber/10 border-accent-amber/20',
      iconClass: 'text-accent-amber',
    };
  }

  if (includesAny(sample, ['עלות', 'billing', 'invoice', 'finance', 'receipt', 'expense'])) {
    return {
      Icon: FileText,
      ringClass: 'bg-accent-green/10 border-accent-green/20',
      iconClass: 'text-accent-green',
    };
  }

  if (includesAny(sample, ['search', 'knowledge', 'ידע', 'חפש', 'find'])) {
    return {
      Icon: Search,
      ringClass: 'bg-accent-cyan/10 border-accent-cyan/20',
      iconClass: 'text-accent-cyan',
    };
  }

  if (includesAny(sample, ['reply', 'email', 'mail', 'מייל', 'reply needed', 'טיוטה'])) {
    return {
      Icon: Mail,
      ringClass: 'bg-accent-indigo/10 border-accent-indigo/20',
      iconClass: 'text-accent-indigo',
    };
  }

  return {
    Icon: Sparkles,
    ringClass: 'bg-accent-purple/10 border-accent-purple/20',
    iconClass: 'text-accent-purple',
  };
}

function getActionVisual(label) {
  const value = String(label || '');

  if (includesAny(value, ['אשר', 'approve', 'שלח', 'send', 'כן'])) {
    return {
      Icon: Check,
      className:
        'border-accent-green/20 bg-accent-green/10 text-accent-green hover:bg-accent-green/14',
    };
  }

  if (includesAny(value, ['פגישה', 'meeting', 'calendar', 'event', 'מועד'])) {
    return {
      Icon: CalendarDays,
      className:
        'border-accent-amber/20 bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/14',
    };
  }

  if (includesAny(value, ['חפש', 'search', 'ידע', 'find'])) {
    return {
      Icon: Search,
      className:
        'border-accent-cyan/20 bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/14',
    };
  }

  if (includesAny(value, ['הכוונה', 'ערוך', 'manual', 'edit', 'שנה'])) {
    return {
      Icon: Pencil,
      className:
        'border-border-light bg-bg-hover text-text-secondary hover:text-text-primary hover:bg-bg-active',
    };
  }

  return {
    Icon: Sparkles,
    className:
      'border-accent-indigo/20 bg-accent-indigo/10 text-accent-indigo hover:bg-accent-indigo/14',
  };
}

function getLastConversationMessage(conv) {
  if (!Array.isArray(conv?.messages) || conv.messages.length === 0) return null;
  return conv.messages[conv.messages.length - 1];
}

function cleanConversationSeed(value) {
  return String(value || '')
    .replace(/\[\[BUTTONS:[\s\S]+?\]\]/gi, '')
    .replace(/\*+/g, ' ')
    .replace(/^[^\w\u0590-\u05FFA-Za-z0-9]+/, '')
    .replace(/[|]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function summarizeConversationTitle(title, preview) {
  const seed = cleanConversationSeed(title) || cleanConversationSeed(preview);
  const lower = seed.toLowerCase();

  const withHebrewMatch = seed.match(/עם\s+([^\s,.;!?]+)/);
  const withEnglishMatch = seed.match(/\bwith\s+([A-Za-z][A-Za-z'-]*)/i);
  const person = withHebrewMatch?.[1] || withEnglishMatch?.[1] || '';

  if (includesAny(lower, ['לו"ז', 'הלוז', 'schedule', 'today plan', 'calendar today'])) {
    return includesAny(lower, ['לו"ז', 'הלוז']) ? 'הלוז להיום' : "Today's schedule";
  }

  if (includesAny(lower, ['add meeting', 'create meeting', 'הוסף פגישה', 'תוסיף לי פגישה', 'פגישה נוספת'])) {
    if (person) {
      return /[A-Za-z]/.test(person) ? `Add meeting with ${person}` : `פגישה עם ${person}`;
    }
    return includesAny(lower, ['פגישה']) ? 'פגישה חדשה' : 'New meeting';
  }

  if (includesAny(lower, ['meeting', 'פגישה', 'calendar', 'schedule'])) {
    if (person) {
      return /[A-Za-z]/.test(person) ? `Meeting with ${person}` : `פגישה עם ${person}`;
    }
    return includesAny(lower, ['פגישה']) ? 'עדכון פגישה' : 'Meeting update';
  }

  if (includesAny(lower, ['cost', 'billing', 'expense', 'finance', 'invoice', 'receipt'])) {
    return 'Cost and billing';
  }

  if (includesAny(lower, ['email', 'reply', 'draft', 'מייל', 'טיוטה', 'השב'])) {
    return includesAny(lower, ['מייל', 'טיוטה']) ? 'טיפול במייל' : 'Email follow-up';
  }

  const words = seed.split(' ').filter(Boolean).slice(0, 5).join(' ');
  return words || 'Conversation';
}

export default function ChatPanel() {
  const [view, setView] = useState('list');
  const [activeConvId, setActiveConvId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [convTitle, setConvTitle] = useState('');
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingConv, setLoadingConv] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const messagesEndRef = useRef(null);

  const { data: conversations, refresh: refreshList } = useApi('/api/chat');

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const openConversation = useCallback(async (id) => {
    setLoadingConv(true);
    setActiveConvId(id);
    setView('chat');

    try {
      const { data } = await apiGet(`/api/chat/${id}`);
      setMessages(data.messages || []);
      setConvTitle(data.title || 'Knowledge Agent');
    } catch (err) {
      console.error('Failed to load conversation', err);
    } finally {
      setLoadingConv(false);
    }
  }, []);

  const startNewConversation = useCallback(async () => {
    try {
      const { data } = await apiPost('/api/chat', { title: 'New conversation' });
      await openConversation(data._id);
      refreshList();
    } catch (err) {
      console.error('Failed to create conversation', err);
    }
  }, [openConversation, refreshList]);

  const submitMessage = useCallback(async (rawContent) => {
    const content = String(rawContent || '').trim();
    if (!content || sending) return;

    const optimisticMsg = {
      _id: `optimistic-${Date.now()}`,
      role: 'user',
      content,
      createdAt: new Date().toISOString(),
    };

    setInputText('');
    setMessages((prev) => [...prev, optimisticMsg]);
    setSending(true);

    let convId = activeConvId;

    try {
      if (!convId) {
        const { data: newConv } = await apiPost('/api/chat', {
          title: 'New conversation',
        });
        convId = newConv._id;
        setActiveConvId(convId);
        setConvTitle(newConv.title || 'Knowledge Agent');
        setView('chat');
      }

      const { data } = await apiPost(`/api/chat/${convId}/messages`, { content });
      setMessages(data.conversation.messages || []);
      setConvTitle(data.conversation.title || 'Knowledge Agent');
      refreshList();
    } catch (err) {
      setMessages((prev) => prev.filter((msg) => msg._id !== optimisticMsg._id));
      console.error('Send message failed', err);
    } finally {
      setSending(false);
    }
  }, [activeConvId, refreshList, sending]);

  const sendMessage = async (e) => {
    e?.preventDefault();
    await submitMessage(inputText);
  };

  const handleSuggestedAction = useCallback(async (label) => {
    await submitMessage(label);
  }, [submitMessage]);

  const deleteConversation = async (id, e) => {
    e?.stopPropagation();
    setDeletingId(id);

    try {
      await apiDelete(`/api/chat/${id}`);

      if (activeConvId === id) {
        setView('list');
        setActiveConvId(null);
        setMessages([]);
        setConvTitle('');
      }

      refreshList();
    } catch (err) {
      console.error('Delete failed', err);
    } finally {
      setDeletingId(null);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const activeDisplayTitle = summarizeConversationTitle(convTitle, messages[messages.length - 1]?.content);
  const activeVisual = getTopicVisual(activeDisplayTitle, messages[messages.length - 1]?.content);

  return (
    <aside className="w-[344px] xl:w-[360px] flex-shrink-0 border-l border-border bg-gradient-to-b from-bg-secondary to-[#0d1119]">
      {view === 'list' && (
        <div className="flex h-full flex-col overflow-hidden">
          <div className="border-b border-border px-4 py-3.5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-2xl border border-accent-indigo/20 bg-accent-indigo/10">
                  <Bot size={15} className="text-accent-indigo" />
                </div>
                <div className="min-w-0">
                  <p className="text-[12px] font-semibold tracking-[0.02em] text-text-primary">
                    Knowledge Agent
                  </p>
                  <p className="text-[10px] uppercase tracking-[0.24em] text-text-muted">
                    Conversations
                  </p>
                </div>
              </div>

              <button
                onClick={startNewConversation}
                className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-accent-indigo/20 bg-accent-indigo px-3 text-[11px] font-medium text-white shadow-[0_12px_24px_rgba(99,102,241,0.22)] transition-all duration-150 hover:bg-indigo-400"
                title="New conversation"
              >
                <Plus size={12} />
                New
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-3 py-3">
            {!conversations?.length ? (
              <div className="flex h-full flex-col items-center justify-center px-6 text-center">
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-[18px] border border-accent-indigo/20 bg-accent-indigo/10">
                  <Sparkles size={18} className="text-accent-indigo" />
                </div>
                <p className="text-[13px] font-medium text-text-primary">No conversations yet</p>
                <button
                  onClick={startNewConversation}
                  className="mt-4 inline-flex h-9 items-center gap-1.5 rounded-xl border border-accent-indigo/20 bg-accent-indigo px-3 text-[11px] font-medium text-white shadow-[0_12px_24px_rgba(99,102,241,0.18)] transition-all duration-150 hover:bg-indigo-400"
                >
                  <Plus size={12} />
                  New conversation
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {conversations.map((conv) => {
                  const lastMessage = getLastConversationMessage(conv);
                  const previewText = stripButtonMarker(lastMessage?.content || '');
                  const displayTitle = summarizeConversationTitle(conv.title, previewText);
                  const direction = detectTextDirection(displayTitle, 'ltr');
                  const visual = getTopicVisual(displayTitle, previewText);

                  return (
                    <div
                      key={conv._id}
                      className={cn(
                        'group rounded-[22px] border transition-all duration-150',
                        activeConvId === conv._id
                          ? 'border-accent-indigo/26 bg-bg-card/90 shadow-[0_14px_30px_rgba(0,0,0,0.18)]'
                          : 'border-border/80 bg-bg-card/60 hover:border-border-light hover:bg-bg-card/85'
                      )}
                    >
                      <div className="flex items-start gap-2 p-2.5">
                        <button
                          onClick={() => openConversation(conv._id)}
                          dir={direction}
                          className={cn(
                            'flex min-w-0 flex-1 items-start gap-3 rounded-[18px] p-1.5 text-left',
                            direction === 'rtl' ? 'text-right' : 'text-left'
                          )}
                        >
                          <div className={cn('mt-0.5 flex h-9 w-9 items-center justify-center rounded-2xl border', visual.ringClass)}>
                            <visual.Icon size={14} className={visual.iconClass} />
                          </div>

                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <p className="min-w-0 flex-1 truncate text-[12px] font-semibold text-text-primary">
                                {displayTitle}
                              </p>
                              <span dir="ltr" className="shrink-0 text-[10px] text-text-muted">
                                {timeAgo(conv.lastActivity)}
                              </span>
                            </div>
                          </div>
                        </button>

                        <button
                          onClick={(e) => deleteConversation(conv._id, e)}
                          disabled={deletingId === conv._id}
                          className="mt-1 flex h-8 w-8 items-center justify-center rounded-xl border border-transparent text-text-muted transition-all duration-150 hover:border-border hover:bg-bg-hover hover:text-text-primary disabled:opacity-50"
                          title="Delete conversation"
                        >
                          {deletingId === conv._id ? (
                            <Loader2 size={12} className="animate-spin" />
                          ) : (
                            <Trash2 size={12} />
                          )}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {view === 'chat' && (
        <div className="flex h-full flex-col overflow-hidden">
          <div className="border-b border-border px-4 py-3">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setView('list')}
                className="flex h-9 w-9 items-center justify-center rounded-xl border border-border/80 bg-bg-card/60 text-text-muted transition-all duration-150 hover:border-border-light hover:bg-bg-hover hover:text-text-primary"
                title="Back"
              >
                <ChevronLeft size={14} />
              </button>

              <div className={cn('flex h-10 w-10 items-center justify-center rounded-2xl border', activeVisual.ringClass)}>
                <activeVisual.Icon size={15} className={activeVisual.iconClass} />
              </div>

              <div className="min-w-0 flex-1">
                <p
                  dir={detectTextDirection(activeDisplayTitle, 'ltr')}
                  className={cn(
                    'truncate text-[12px] font-semibold tracking-[0.02em] text-text-primary',
                    detectTextDirection(activeDisplayTitle, 'ltr') === 'rtl' ? 'text-right' : 'text-left'
                  )}
                >
                  {activeDisplayTitle || 'Knowledge Agent'}
                </p>
                <p className="text-[10px] uppercase tracking-[0.24em] text-text-muted">
                  Live thread
                </p>
              </div>

              <button
                onClick={startNewConversation}
                className="flex h-9 w-9 items-center justify-center rounded-xl border border-border/80 bg-bg-card/60 text-text-muted transition-all duration-150 hover:border-border-light hover:bg-bg-hover hover:text-text-primary"
                title="New conversation"
              >
                <Plus size={13} />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-4">
            {loadingConv ? (
              <div className="flex h-full items-center justify-center">
                <Loader2 size={18} className="animate-spin text-text-muted" />
              </div>
            ) : messages.length === 0 ? (
              <div className="flex h-full items-center justify-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-[20px] border border-accent-indigo/20 bg-accent-indigo/10">
                  <Bot size={18} className="text-accent-indigo" />
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {messages.map((msg, idx) => {
                  const parsed = parseButtonMarker(msg.content);
                  const visibleText = parsed.text;
                  const direction = detectTextDirection(
                    visibleText || msg.content,
                    msg.role === 'assistant' ? 'rtl' : 'ltr'
                  );
                  const isRtl = direction === 'rtl';
                  const visual = getTopicVisual(convTitle, visibleText || msg.content);

                  return (
                    <div
                      key={msg._id || idx}
                      className={cn(
                        'flex items-end gap-2.5',
                        msg.role === 'user' ? 'justify-end' : 'justify-start'
                      )}
                    >
                      {msg.role === 'assistant' && (
                        <div className={cn('flex h-8 w-8 items-center justify-center rounded-2xl border flex-shrink-0', visual.ringClass)}>
                          <visual.Icon size={13} className={visual.iconClass} />
                        </div>
                      )}

                      <div className="max-w-[82%]">
                        {(visibleText || '').trim() ? (
                          <div
                            dir={direction}
                            className={cn(
                              'rounded-[22px] px-3.5 py-3 shadow-[0_12px_30px_rgba(0,0,0,0.14)]',
                              isRtl ? 'text-right' : 'text-left',
                              msg.role === 'user'
                                ? 'bg-accent-indigo text-white rounded-br-md shadow-[0_16px_36px_rgba(99,102,241,0.22)]'
                                : 'border border-border/80 bg-bg-card/92 text-text-primary rounded-bl-md'
                            )}
                          >
                            <AgentRichText
                              text={visibleText}
                              fallbackDirection={msg.role === 'assistant' ? 'rtl' : 'ltr'}
                              className="space-y-2"
                              blockClassName={cn(
                                'text-[12px] leading-6',
                                msg.role === 'user' ? 'text-white' : 'text-text-primary'
                              )}
                            />

                            <div
                              dir="ltr"
                              className={cn(
                                'mt-2 text-[10px]',
                                isRtl ? 'text-right' : 'text-left',
                                msg.role === 'user' ? 'text-white/60' : 'text-text-muted'
                              )}
                            >
                              {msg.createdAt ? timeAgo(msg.createdAt) : ''}
                            </div>
                          </div>
                        ) : null}

                        {msg.role === 'assistant' && parsed.buttons.length > 0 ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {parsed.buttons.map((label) => {
                              const buttonVisual = getActionVisual(label);
                              return (
                                <button
                                  key={`${msg._id || idx}-${label}`}
                                  onClick={() => handleSuggestedAction(label)}
                                  disabled={sending}
                                  className={cn(
                                    'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] font-medium transition-all duration-150 disabled:opacity-50',
                                    buttonVisual.className
                                  )}
                                >
                                  <buttonVisual.Icon size={12} />
                                  <span dir={detectTextDirection(label, 'rtl')}>{label}</span>
                                </button>
                              );
                            })}
                          </div>
                        ) : null}
                      </div>

                      {msg.role === 'user' && (
                        <div className="flex h-8 w-8 items-center justify-center rounded-2xl border border-border/80 bg-bg-hover flex-shrink-0">
                          <User size={13} className="text-text-muted" />
                        </div>
                      )}
                    </div>
                  );
                })}

                {sending && (
                  <div className="flex items-end gap-2.5">
                    <div className={cn('flex h-8 w-8 items-center justify-center rounded-2xl border', activeVisual.ringClass)}>
                      <activeVisual.Icon size={13} className={activeVisual.iconClass} />
                    </div>
                    <div className="rounded-[22px] rounded-bl-md border border-border/80 bg-bg-card/92 px-3.5 py-3">
                      <div className="flex items-center gap-1.5">
                        <div className="h-1.5 w-1.5 rounded-full bg-accent-indigo animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="h-1.5 w-1.5 rounded-full bg-accent-indigo animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="h-1.5 w-1.5 rounded-full bg-accent-indigo animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          <div className="border-t border-border bg-[#0d1118]/90 px-4 py-3">
            <form onSubmit={sendMessage} className="flex items-end gap-2">
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Write a message"
                rows={1}
                disabled={sending}
                dir={detectTextDirection(inputText, 'rtl')}
                className={cn(
                  'min-h-[42px] max-h-[120px] flex-1 resize-none appearance-none rounded-[18px] border border-border/80 bg-bg-card/88 px-3.5 py-2.5 text-[12px] text-text-primary transition-all duration-150 focus:border-accent-indigo/60 focus:outline-none focus:ring-1 focus:ring-accent-indigo/20',
                  detectTextDirection(inputText, 'rtl') === 'rtl' ? 'text-right' : 'text-left',
                  'placeholder:text-text-muted disabled:opacity-50'
                )}
                style={{
                  height: 'auto',
                  overflowY: 'auto',
                  color: '#e8edf5',
                  backgroundColor: 'rgba(22,26,38,0.92)',
                  WebkitTextFillColor: '#e8edf5',
                  caretColor: '#e8edf5',
                }}
                onInput={(e) => {
                  e.target.style.height = 'auto';
                  e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
                }}
              />

              <button
                type="submit"
                disabled={!inputText.trim() || sending}
                className="flex h-[42px] w-[42px] items-center justify-center rounded-[16px] bg-accent-indigo text-white shadow-[0_12px_24px_rgba(99,102,241,0.2)] transition-all duration-150 hover:bg-indigo-400 disabled:opacity-40"
                title="Send"
              >
                {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              </button>
            </form>
          </div>
        </div>
      )}
    </aside>
  );
}
