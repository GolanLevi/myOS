import express from 'express';
import Finance from '../models/Finance.js';
import { protect } from '../middleware/auth.js';

const router = express.Router();
router.use(protect);

// GET /api/finances/stats
router.get('/stats', async (req, res) => {
  try {
    const uid = req.user._id;
    const now = new Date();
    const startOfDay   = new Date(now.setHours(0, 0, 0, 0));
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);

    const [todayCosts, monthCosts, allExpenses] = await Promise.all([
      Finance.aggregate([{ $match: { userId: uid, type: 'expense', date: { $gte: startOfDay } } }, { $group: { _id: null, total: { $sum: '$amount' } } }]),
      Finance.aggregate([{ $match: { userId: uid, type: 'expense', date: { $gte: startOfMonth } } }, { $group: { _id: null, total: { $sum: '$amount' } } }]),
      Finance.find({ userId: uid, type: 'expense', date: { $gte: startOfMonth } }),
    ]);

    const todayTotal = todayCosts[0]?.total || 0;
    const monthTotal = monthCosts[0]?.total || 0;
    const monthlyBudget = 50; // $50/month

    res.json({
      todayCost:     parseFloat(todayTotal.toFixed(4)),
      monthCost:     parseFloat(monthTotal.toFixed(4)),
      monthlyBudget,
      budgetUsedPct: Math.round((monthTotal / monthlyBudget) * 100),
      count:         allExpenses.length,
    });
  } catch (err) { res.status(500).json({ message: err.message }); }
});

// GET /api/finances  — list + chart data
router.get('/', async (req, res) => {
  try {
    const { days = 30 } = req.query;
    const since = new Date();
    since.setDate(since.getDate() - parseInt(days));
    const items = await Finance.find({ userId: req.user._id, date: { $gte: since } }).sort({ date: -1 });
    res.json(items);
  } catch (err) { res.status(500).json({ message: err.message }); }
});

router.post('/', async (req, res) => {
  try {
    const item = await Finance.create({ ...req.body, userId: req.user._id });
    res.status(201).json(item);
  } catch (err) { res.status(500).json({ message: err.message }); }
});

export default router;
