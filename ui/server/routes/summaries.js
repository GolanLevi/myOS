import express from 'express';
import Summary from '../models/Summary.js';
import { protect } from '../middleware/auth.js';

const router = express.Router();
router.use(protect);

router.get('/', async (req, res) => {
  try {
    const { source, unread } = req.query;
    const filter = { userId: req.user._id };
    if (source) filter.source = source;
    if (unread === 'true') filter.read = false;
    const items = await Summary.find(filter).sort({ createdAt: -1 }).limit(50);
    res.json(items);
  } catch (err) { res.status(500).json({ message: err.message }); }
});

router.patch('/:id/read', async (req, res) => {
  try {
    const s = await Summary.findOneAndUpdate(
      { _id: req.params.id, userId: req.user._id },
      { read: true },
      { new: true }
    );
    res.json(s);
  } catch (err) { res.status(500).json({ message: err.message }); }
});

router.post('/', async (req, res) => {
  try {
    const item = await Summary.create({ ...req.body, userId: req.user._id });
    res.status(201).json(item);
  } catch (err) { res.status(500).json({ message: err.message }); }
});

router.delete('/:id', async (req, res) => {
  try {
    await Summary.findOneAndDelete({ _id: req.params.id, userId: req.user._id });
    res.json({ success: true });
  } catch (err) { res.status(500).json({ message: err.message }); }
});

export default router;
