import express from 'express';
import Agent from '../models/Agent.js';
import { protect } from '../middleware/auth.js';

const router = express.Router();
router.use(protect);

router.get('/', async (req, res) => {
  try {
    const agents = await Agent.find({ userId: req.user._id }).sort({ lastRun: -1 });
    res.json(agents);
  } catch (err) { res.status(500).json({ message: err.message }); }
});

router.get('/stats', async (req, res) => {
  try {
    const uid = req.user._id;
    const total   = await Agent.countDocuments({ userId: uid });
    const active  = await Agent.countDocuments({ userId: uid, status: 'active' });
    const paused  = await Agent.countDocuments({ userId: uid, status: 'paused' });
    const error   = await Agent.countDocuments({ userId: uid, status: 'error' });
    res.json({ total, active, paused, error });
  } catch (err) { res.status(500).json({ message: err.message }); }
});

router.post('/', async (req, res) => {
  try {
    const agent = await Agent.create({ ...req.body, userId: req.user._id });
    res.status(201).json(agent);
  } catch (err) { res.status(500).json({ message: err.message }); }
});

router.patch('/:id', async (req, res) => {
  try {
    const agent = await Agent.findOneAndUpdate(
      { _id: req.params.id, userId: req.user._id },
      req.body,
      { new: true }
    );
    if (!agent) return res.status(404).json({ message: 'Agent not found' });
    res.json(agent);
  } catch (err) { res.status(500).json({ message: err.message }); }
});

router.delete('/:id', async (req, res) => {
  try {
    await Agent.findOneAndDelete({ _id: req.params.id, userId: req.user._id });
    res.json({ success: true });
  } catch (err) { res.status(500).json({ message: err.message }); }
});

export default router;
