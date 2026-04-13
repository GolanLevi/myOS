import dotenv from 'dotenv';
import mongoose from 'mongoose';
import User         from '../models/User.js';
import Agent        from '../models/Agent.js';
import Notification from '../models/Notification.js';
import Approval     from '../models/Approval.js';
import Finance      from '../models/Finance.js';
import Summary      from '../models/Summary.js';
import Integration  from '../models/Integration.js';
import Task         from '../models/Task.js';
import Activity     from '../models/Activity.js';

dotenv.config();

const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/myos_dashboard';

async function seed() {
  await mongoose.connect(MONGODB_URI);
  console.log('🌱 Connected to MongoDB — seeding...');

  // Clear all collections
  await Promise.all([
    User.deleteMany({}), Agent.deleteMany({}), Notification.deleteMany({}),
    Approval.deleteMany({}), Finance.deleteMany({}), Summary.deleteMany({}),
    Integration.deleteMany({}), Task.deleteMany({}), Activity.deleteMany({}),
  ]);

  // Create demo user
  const user = await User.create({ name: 'Golan Levi', email: 'golan@myos.dev', password: 'password123', role: 'admin' });
  const uid = user._id;
  console.log('👤 Created user: golan@myos.dev / password123');

  // Agents
  const agents = await Agent.insertMany([
    { userId: uid, name: 'Secretariat', type: 'SecretariatAgent', description: 'Email triage and calendar management', status: 'active', color: '#6366f1', lastAction: 'Drafted reply to John Smith', lastRun: new Date(Date.now() - 3 * 60000), actionsToday: 12, totalActions: 487, costToday: 0.043 },
    { userId: uid, name: 'Finance',     type: 'FinanceAgent',     description: 'Expense tracking and budget alerts', status: 'active', color: '#10b981', lastAction: 'Parsed AWS invoice $34.20', lastRun: new Date(Date.now() - 18 * 60000), actionsToday: 4, totalActions: 91, costToday: 0.012 },
    { userId: uid, name: 'Knowledge',   type: 'KnowledgeAgent',   description: 'RAG memory store over personal data', status: 'idle',   color: '#8b5cf6', lastAction: 'Indexed 23 emails', lastRun: new Date(Date.now() - 2 * 3600000), actionsToday: 2, totalActions: 210, costToday: 0.008 },
    { userId: uid, name: 'Research',    type: 'WebSearchAgent',   description: 'Background web research on topics', status: 'paused', color: '#f59e0b', lastAction: 'Research: AI funding trends', lastRun: new Date(Date.now() - 5 * 3600000), actionsToday: 0, totalActions: 34, costToday: 0 },
  ]);

  // Notifications
  await Notification.insertMany([
    { userId: uid, title: 'Invoice $485 auto-payment requires approval', body: 'Wham → Freelance payment', source: 'FinanceAgent', severity: 'high' },
    { userId: uid, title: 'Server cost anomaly detected — 2.2x above baseline', body: 'AWS EC2 costs spiked unexpectedly this week', source: 'FinanceAgent', severity: 'critical' },
    { userId: uid, title: 'Weekly report draft ready for review', body: 'Content Agent prepared your weekly summary', source: 'SecretariatAgent', severity: 'low' },
  ]);

  // Approvals
  await Approval.insertMany([
    { userId: uid, agentName: 'SecretariatAgent', actionType: 'send_email',   title: 'Send follow-up email to 12 leads', description: 'CRM Agent · 78% confidence · Email draft ready to send to 12 prospective clients', confidence: 78, status: 'pending' },
    { userId: uid, agentName: 'SecretariatAgent', actionType: 'create_event', title: 'Reschedule Tuesday standup to Wednesday', description: 'Calendar Agent · 94% confidence · Conflict detected, proposing Wednesday 10:00am', confidence: 94, status: 'pending' },
    { userId: uid, agentName: 'SecretariatAgent', actionType: 'create_draft', title: 'Update pricing page copy', description: 'Content Agent · 71% confidence · Minor copy changes based on competitor analysis', confidence: 71, status: 'pending' },
  ]);

  // Finances — 30 days of data
  const financeEntries = [];
  const providers = [
    { provider: 'gemini',    model: 'gemini-2.0-flash',   baseIn: 0.075, baseOut: 0.30,  agentName: 'SecretariatAgent', category: 'LLM API' },
    { provider: 'anthropic', model: 'claude-3-5-haiku',   baseIn: 0.80,  baseOut: 4.00,  agentName: 'SecretariatAgent', category: 'LLM API' },
    { provider: 'groq',      model: 'llama-3.3-70b',      baseIn: 0.59,  baseOut: 0.79,  agentName: 'KnowledgeAgent',   category: 'LLM API' },
    { provider: 'aws',       model: '',                    baseIn: 0,     baseOut: 0,     agentName: 'FinanceAgent',     category: 'Infrastructure', fixedAmount: 2.3 },
    { provider: 'mongodb',   model: '',                    baseIn: 0,     baseOut: 0,     agentName: 'system',           category: 'Infrastructure', fixedAmount: 0.0 },
  ];
  for (let d = 0; d < 30; d++) {
    const date = new Date(); date.setDate(date.getDate() - d);
    for (const p of providers) {
      if (Math.random() > 0.6) {
        const inTokens  = Math.floor(Math.random() * 5000) + 200;
        const outTokens = Math.floor(Math.random() * 2000) + 100;
        const amount = p.fixedAmount !== undefined
          ? p.fixedAmount + (Math.random() * 0.5 - 0.25)
          : parseFloat(((inTokens * p.baseIn + outTokens * p.baseOut) / 1_000_000).toFixed(6));
        financeEntries.push({ userId: uid, agentName: p.agentName, category: p.category, provider: p.provider, model: p.model, amount, type: 'expense', inputTokens: inTokens, outputTokens: outTokens, date });
      }
    }
  }
  await Finance.insertMany(financeEntries);

  // Summaries
  await Summary.insertMany([
    { userId: uid, agentName: 'SecretariatAgent', source: 'gmail',    title: '3 interview invitations this week', content: 'You received interview requests from TechCorp, StartupX, and FinAI. TechCorp is earliest — they want to schedule by Thursday.', sentiment: 'positive', tags: ['jobs', 'urgent'], priority: 'high' },
    { userId: uid, agentName: 'KnowledgeAgent',   source: 'linkedin', title: 'AI agent frameworks gaining traction', content: 'LangGraph and CrewAI surged in LinkedIn discussions. 5 of your connections shared posts about agent orchestration this week.', sentiment: 'positive', tags: ['ai', 'research'], priority: 'medium' },
    { userId: uid, agentName: 'SecretariatAgent', source: 'gmail',    title: 'Pending invoice from AWS — $34.20', content: 'AWS invoice for March usage. EC2 t3.medium × 730h = $30.12, data transfer = $4.08. 12% above last month.', sentiment: 'neutral', tags: ['finance', 'aws'], priority: 'medium', read: true },
    { userId: uid, agentName: 'KnowledgeAgent',   source: 'twitter',  title: 'Gemini 2.0 Flash pricing drop', content: 'Google announced 50% price reduction on Gemini 2.0 Flash effective immediately. Major cost saving opportunity for your stack.', sentiment: 'positive', tags: ['ai', 'cost'], priority: 'high' },
    { userId: uid, agentName: 'SecretariatAgent', source: 'gmail',    title: 'Q1 contractor invoices due', content: '2 contractors have outstanding invoices: Design Studio ($1,200) due Apr 10, DevOps Freelancer ($850) due Apr 8.', sentiment: 'neutral', tags: ['finance', 'payments'], priority: 'high' },
  ]);

  // Integrations
  await Integration.insertMany([
    { userId: uid, service: 'gmail',            category: 'google',       displayName: 'Gmail',            description: 'Read, triage and draft email replies', status: 'connected', lastSync: new Date(Date.now() - 4 * 60000), connectedAt: new Date(Date.now() - 30 * 86400000) },
    { userId: uid, service: 'google_calendar',  category: 'google',       displayName: 'Google Calendar',  description: 'Create events and check availability',   status: 'connected', lastSync: new Date(Date.now() - 4 * 60000), connectedAt: new Date(Date.now() - 30 * 86400000) },
    { userId: uid, service: 'google_drive',     category: 'google',       displayName: 'Google Drive',     description: 'Read and summarize documents',            status: 'disconnected', lastSync: null },
    { userId: uid, service: 'twitter',          category: 'social',       displayName: 'Twitter / X',      description: 'Monitor mentions and DMs',                status: 'disconnected', lastSync: null },
    { userId: uid, service: 'linkedin',         category: 'social',       displayName: 'LinkedIn',         description: 'Track connection requests and messages',  status: 'disconnected', lastSync: null },
    { userId: uid, service: 'instagram',        category: 'social',       displayName: 'Instagram',        description: 'Monitor DMs and comments',                status: 'disconnected', lastSync: null },
    { userId: uid, service: 'plaid',            category: 'finance',      displayName: 'Plaid (Banking)',  description: 'Connect bank accounts for expense tracking', status: 'disconnected', lastSync: null },
    { userId: uid, service: 'saltedge',         category: 'finance',      displayName: 'Salt Edge',        description: 'European open banking connector',         status: 'disconnected', lastSync: null },
    { userId: uid, service: 'notion',           category: 'productivity', displayName: 'Notion',           description: 'Sync tasks and notes',                    status: 'disconnected', lastSync: null },
    { userId: uid, service: 'slack',            category: 'productivity', displayName: 'Slack',            description: 'Monitor channels and DMs',                status: 'disconnected', lastSync: null },
    { userId: uid, service: 'whatsapp',         category: 'productivity', displayName: 'WhatsApp (WAHA)',  description: 'AI triage for WhatsApp messages',         status: 'disconnected', lastSync: null },
  ]);

  // Tasks
  await Task.insertMany([
    { userId: uid, agentName: 'SecretariatAgent', title: 'Reply to TechCorp interview invitation', priority: 'urgent', status: 'pending', tags: ['email', 'jobs'] },
    { userId: uid, agentName: 'FinanceAgent',     title: 'Review AWS billing anomaly', priority: 'high', status: 'running', tags: ['finance', 'aws'] },
    { userId: uid, agentName: 'system',           title: 'Wire user_config.json into system prompt', priority: 'high', status: 'pending', tags: ['dev', 'myos'] },
    { userId: uid, agentName: 'KnowledgeAgent',   title: 'Index last 90 days of email into ChromaDB', priority: 'medium', status: 'paused', tags: ['rag', 'memory'] },
    { userId: uid, agentName: 'SecretariatAgent', title: 'Pay Design Studio invoice $1,200', priority: 'high', status: 'pending', tags: ['finance'] },
    { userId: uid, agentName: 'system',           title: 'Set up LangSmith tracing', priority: 'medium', status: 'done', tags: ['dev', 'observability'], completedAt: new Date(Date.now() - 86400000) },
    { userId: uid, agentName: 'SecretariatAgent', title: 'Draft Q1 performance summary', priority: 'low', status: 'pending', tags: ['email'] },
  ]);

  // Activity timeline — last 48h
  const ACTION_MINUTES = { send_email: 5, create_event: 3, email_triage_ignore: 1, draft_created: 8, finance_parsed: 4, query_kb: 2 };
  const activityLog = [
    { agentName: 'KnowledgeAgent',   action: 'query_kb',            description: 'Synced 48 contacts from HubSpot', minutesSaved: 3, status: 'success', minutesAgo: 15 },
    { agentName: 'SecretariatAgent', action: 'draft_created',       description: 'Generated weekly analytics summary', minutesSaved: 8, status: 'success', minutesAgo: 34 },
    { agentName: 'SecretariatAgent', action: 'create_event',        description: 'Failed to connect to 3rd API', minutesSaved: 0, status: 'failed', minutesAgo: 41 },
    { agentName: 'SecretariatAgent', action: 'email_triage_ignore', description: 'Auto-categorized 22 inbox items', minutesSaved: 22, status: 'success', minutesAgo: 62 },
    { agentName: 'FinanceAgent',     action: 'finance_parsed',      description: 'Parsed AWS invoice $34.20', minutesSaved: 4, status: 'success', minutesAgo: 95 },
    { agentName: 'SecretariatAgent', action: 'send_email',          description: 'Sent reply to David Re: partnership', minutesSaved: 5, status: 'approved', minutesAgo: 140 },
    { agentName: 'SecretariatAgent', action: 'create_event',        description: 'Created "Product Review" event Thursday 3pm', minutesSaved: 3, status: 'approved', minutesAgo: 230 },
    { agentName: 'KnowledgeAgent',   action: 'query_kb',            description: 'Indexed 23 new email threads', minutesSaved: 12, status: 'success', minutesAgo: 310 },
    { agentName: 'SecretariatAgent', action: 'draft_created',       description: 'Drafted response to recruiter at Stripe', minutesSaved: 8, status: 'success', minutesAgo: 420 },
    { agentName: 'FinanceAgent',     action: 'finance_parsed',      description: 'Detected $485 invoice — awaiting approval', minutesSaved: 0, status: 'pending', minutesAgo: 500 },
  ];

  await Activity.insertMany(activityLog.map(a => ({
    userId:      uid,
    agentName:   a.agentName,
    action:      a.action,
    description: a.description,
    status:      a.status,
    minutesSaved: a.minutesSaved,
    createdAt:   new Date(Date.now() - a.minutesAgo * 60000),
  })));

  console.log('✅ Seed complete!');
  console.log('─────────────────────────────────────');
  console.log('Login:  golan@myos.dev');
  console.log('Pass:   password123');
  console.log('URL:    http://localhost:5173');
  console.log('─────────────────────────────────────');
  await mongoose.disconnect();
}

seed().catch(err => { console.error(err); process.exit(1); });
