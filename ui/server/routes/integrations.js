import express from 'express';
import Integration from '../models/Integration.js';
import { protect } from '../middleware/auth.js';

const router = express.Router();
router.use(protect);

router.get('/', async (req, res) => {
  try {
    const items = await Integration.find({ userId: req.user._id }).sort({ category: 1, displayName: 1 });
    res.json(items);
  } catch (err) { res.status(500).json({ message: err.message }); }
});

router.post('/connect', async (req, res) => {
  try {
    const { service } = req.body;
    const integration = await Integration.findOneAndUpdate(
      { userId: req.user._id, service },
      { status: 'connected', connectedAt: new Date(), lastSync: new Date() },
      { new: true, upsert: false }
    );
    if (!integration) return res.status(404).json({ message: 'Integration not found' });
    res.json(integration);
  } catch (err) { res.status(500).json({ message: err.message }); }
});

router.post('/disconnect', async (req, res) => {
  try {
    const { service } = req.body;
    const integration = await Integration.findOneAndUpdate(
      { userId: req.user._id, service },
      { status: 'disconnected', accessToken: '', refreshToken: '', connectedAt: null },
      { new: true }
    );
    if (!integration) return res.status(404).json({ message: 'Integration not found' });
    res.json(integration);
  } catch (err) { res.status(500).json({ message: err.message }); }
});

export default router;
