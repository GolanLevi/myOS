import express from 'express';
import Activity from '../models/Activity.js';
import { protect } from '../middleware/auth.js';

const router = express.Router();
router.use(protect);

router.get('/', async (req, res) => {
  try {
    const { limit = 30, page = 1 } = req.query;
    const skip = (parseInt(page) - 1) * parseInt(limit);

    // Today boundaries
    const startOfToday = new Date();
    startOfToday.setHours(0, 0, 0, 0);

    const [items, total, savedAgg, savedTodayAgg] = await Promise.all([
      Activity.find({ userId: req.user._id }).sort({ createdAt: -1 }).skip(skip).limit(parseInt(limit)),
      Activity.countDocuments({ userId: req.user._id }),
      // All-time hours saved
      Activity.aggregate([
        { $match: { userId: req.user._id } },
        { $group: { _id: null, totalMinutes: { $sum: '$minutesSaved' } } },
      ]),
      // Today's hours saved
      Activity.aggregate([
        { $match: { userId: req.user._id, createdAt: { $gte: startOfToday } } },
        { $group: { _id: null, totalMinutes: { $sum: '$minutesSaved' } } },
      ]),
    ]);

    const totalMinutesSaved = savedAgg[0]?.totalMinutes || 0;
    const todayMinutesSaved = savedTodayAgg[0]?.totalMinutes || 0;

    res.json({
      items,
      total,
      page: parseInt(page),
      pages: Math.ceil(total / parseInt(limit)),
      hoursSaved:      parseFloat((totalMinutesSaved / 60).toFixed(1)),
      hoursSavedToday: parseFloat((todayMinutesSaved  / 60).toFixed(1)),
    });
  } catch (err) { res.status(500).json({ message: err.message }); }
});

export default router;
