import express from 'express';
import Conversation from '../models/Conversation.js';
import { protect } from '../middleware/auth.js';

const router = express.Router();
router.use(protect);

function normalizeConversationSeed(value) {
  return String(value || '')
    .replace(/\[\[BUTTONS:[\s\S]+?\]\]/gi, '')
    .replace(/\*+/g, ' ')
    .replace(/^[^A-Za-z0-9\u0590-\u05FF]+/u, '')
    .replace(/[|]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function includesAny(value, needles) {
  const normalized = String(value || '').toLowerCase();
  return needles.some((needle) => normalized.includes(needle));
}

function deriveConversationTitle(existingTitle, latestUserMessage, latestAssistantMessage = '') {
  const currentTitle = normalizeConversationSeed(existingTitle);
  const fallbackSeed = normalizeConversationSeed(latestUserMessage) || normalizeConversationSeed(latestAssistantMessage);
  const seed = currentTitle && currentTitle !== 'New conversation' ? currentTitle : fallbackSeed;
  const lower = seed.toLowerCase();

  const withHebrewMatch = seed.match(/עם\s+([^\s,.;!?]+)/);
  const withEnglishMatch = seed.match(/\bwith\s+([A-Za-z][A-Za-z'-]*)/i);
  const person = withHebrewMatch?.[1] || withEnglishMatch?.[1] || '';

  if (includesAny(lower, ['לו"ז', 'הלוז', 'schedule', 'today plan', 'calendar today'])) {
    return includesAny(lower, ['לו"ז', 'הלוז']) ? 'הלוז להיום' : "Today's schedule";
  }

  if (includesAny(lower, ['dinner', 'ארוחת ערב'])) {
    if (person) {
      return /[A-Za-z]/.test(person) ? `Dinner with ${person}` : `ארוחת ערב עם ${person}`;
    }
    return includesAny(lower, ['ארוחת ערב']) ? 'ארוחת ערב' : 'Dinner plan';
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

function resolveWorkflowUserId(user) {
  if (!user?._id) return '';
  return String(user.role || '').toLowerCase() === 'admin'
    ? 'admin'
    : user._id.toString();
}

// GET /api/chat - list conversations (title + lastActivity, no messages)
router.get('/', async (req, res) => {
  try {
    const conversations = await Conversation.find(
      { userId: req.user._id },
      { title: 1, lastActivity: 1, createdAt: 1, messages: { $slice: -1 } }
    ).sort({ lastActivity: -1 }).limit(50);
    res.json(conversations);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// POST /api/chat - create new conversation
router.post('/', async (req, res) => {
  try {
    const { title = 'New conversation', firstMessage } = req.body;
    const messages = firstMessage ? [{ role: 'user', content: firstMessage }] : [];
    const conv = await Conversation.create({
      userId: req.user._id,
      title: deriveConversationTitle(title || 'New conversation', firstMessage || '', ''),
      messages,
    });
    res.status(201).json(conv);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// GET /api/chat/:id - get full conversation with messages
router.get('/:id', async (req, res) => {
  try {
    const conv = await Conversation.findOne({ _id: req.params.id, userId: req.user._id });
    if (!conv) return res.status(404).json({ message: 'Conversation not found' });
    res.json(conv);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// POST /api/chat/:id/messages - send a message and get AI reply
router.post('/:id/messages', async (req, res) => {
  try {
    const { content } = req.body;
    if (!content?.trim()) return res.status(400).json({ message: 'Message content required' });

    const conv = await Conversation.findOne({ _id: req.params.id, userId: req.user._id });
    if (!conv) return res.status(404).json({ message: 'Conversation not found' });

    conv.messages.push({ role: 'user', content: content.trim() });

    let aiReply = null;
    try {
      const { default: axios } = await import('axios');
      const pythonApiUrl = process.env.PYTHON_API_URL || 'http://localhost:8000';
      const response = await axios.post(
        `${pythonApiUrl}/ask`,
        { text: content, source: 'dashboard', user_id: resolveWorkflowUserId(req.user) },
        { timeout: 15000 }
      );
      aiReply = response.data?.answer || response.data?.message || null;
    } catch {
      aiReply = generateStubReply(content, conv.messages);
    }

    if (aiReply) {
      conv.messages.push({ role: 'assistant', content: aiReply });
    }

    conv.title = deriveConversationTitle(conv.title, content.trim(), aiReply || '');
    conv.lastActivity = new Date();
    await conv.save();

    res.json({
      conversation: conv,
      reply: aiReply,
    });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// DELETE /api/chat/:id - delete conversation
router.delete('/:id', async (req, res) => {
  try {
    await Conversation.findOneAndDelete({ _id: req.params.id, userId: req.user._id });
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// PATCH /api/chat/:id - rename conversation
router.patch('/:id', async (req, res) => {
  try {
    const { title } = req.body;
    const conv = await Conversation.findOneAndUpdate(
      { _id: req.params.id, userId: req.user._id },
      { title },
      { new: true }
    );
    if (!conv) return res.status(404).json({ message: 'Not found' });
    res.json(conv);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

function generateStubReply(userMessage) {
  const lower = userMessage.toLowerCase();

  if (lower.includes('cost') || lower.includes('expense') || lower.includes('עלות')) {
    return "Based on the cost data in the system, your monthly AI spend is tracked in the Cost & Value page. Today's costs are calculated from actual LLM API calls logged per agent.";
  }
  if (lower.includes('agent') || lower.includes('סוכן')) {
    return 'You currently have 4 agents registered: Secretariat (active), Finance (active), Knowledge (idle), and Research (paused). You can manage them from the Admin page.';
  }
  if (lower.includes('email') || lower.includes('מייל')) {
    return 'The SecretariatAgent monitors your Gmail inbox. Any new emails are classified and triaged automatically. Pending approvals for email actions appear on the Today page.';
  }
  if (lower.includes('time') || lower.includes('שעות') || lower.includes('חסכון')) {
    return 'Hours saved are calculated from the activity log - each agent action has an estimated time saving. You can see the full breakdown on the Timeline page.';
  }
  if (['שלום', 'hello', 'hi', 'hey'].some((word) => lower.includes(word))) {
    return 'שלום! אני סוכן הידע של myOS. אני יכול לעזור לך לחפש מידע, לענות על שאלות על הסוכנים שלך, ולגשת לזיכרון הארגוני. כיצד אוכל לעזור?';
  }
  return `Knowledge Agent (offline mode): The Python backend is not reachable right now. Connect it at http://localhost:8000 to get real AI responses from your LangGraph agents. Your question was: "${userMessage.slice(0, 80)}..."`;
}

export default router;
