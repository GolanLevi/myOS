import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { connectDB } from './lib/db.js';
import authRoutes         from './routes/auth.js';
import agentRoutes        from './routes/agents.js';
import notificationRoutes from './routes/notifications.js';
import approvalRoutes     from './routes/approvals.js';
import financeRoutes      from './routes/finances.js';
import summaryRoutes      from './routes/summaries.js';
import integrationRoutes  from './routes/integrations.js';
import taskRoutes         from './routes/tasks.js';
import activityRoutes     from './routes/activity.js';
import chatRoutes         from './routes/chat.js';
import liveDashboardRoutes from './routes/liveDashboard.js';

dotenv.config();

const app  = express();
const PORT = process.env.PORT || 5000;

app.use(cors({ origin: ['http://localhost:5173', 'http://localhost:3000'], credentials: true }));
app.use(express.json());

connectDB();

app.use('/api/auth',          authRoutes);
app.use('/api/agents',        agentRoutes);
app.use('/api/notifications', notificationRoutes);
app.use('/api/approvals',     approvalRoutes);
app.use('/api/finances',      financeRoutes);
app.use('/api/summaries',     summaryRoutes);
app.use('/api/integrations',  integrationRoutes);
app.use('/api/tasks',         taskRoutes);
app.use('/api/activity',      activityRoutes);
app.use('/api/chat',          chatRoutes);
app.use('/api/live',          liveDashboardRoutes);

app.get('/api/health', (_, res) => res.json({ status: 'ok', ts: new Date().toISOString() }));

app.listen(PORT, () => console.log(`🚀 myOS Server → http://localhost:${PORT}`));
