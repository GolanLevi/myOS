import express from 'express';
import Approval from '../models/Approval.js';
import Activity from '../models/Activity.js';
import { protect } from '../middleware/auth.js';

const router = express.Router();
router.use(protect);

router.get('/', async (req, res) => {
  try {
    const { status = 'pending' } = req.query;
    const items = await Approval.find({ userId: req.user._id, status }).sort({ createdAt: -1 });
    
    // Fallback extraction for legacy/seed data lacking sender properties
    const enriched = items.map(doc => {
      const item = doc.toObject();
      if (!item.senderName) {
        const str = item.content || item.description || '';
        const match = str.match(/from\s+([^\s(]+)\s+\(([^)]+)\)/i) || str.match(/שולח:\s*(.+?)(?:\n|$)/);
        if (match) {
          item.senderName = match[1] ? match[1].replace(/[[\]]/g, '').trim() : '';
          item.senderEmail = match[2] ? match[2].trim() : '';
        } else {
          item.senderName = 'Unknown Sender';
        }
      }
      return item;
    });

    res.json(enriched);
  } catch (err) { res.status(500).json({ message: err.message }); }
});

router.patch('/:id/approve', async (req, res) => {
  try {
    const approval = await Approval.findOneAndUpdate(
      { _id: req.params.id, userId: req.user._id },
      { status: 'approved', resolvedAt: new Date() },
      { new: true }
    );
    if (!approval) return res.status(404).json({ message: 'Not found' });
    // Log to activity
    await Activity.create({
      userId:      req.user._id,
      agentName:   approval.agentName,
      action:      approval.actionType,
      description: `Approved: ${approval.title}`,
      status:      'approved',
      minutesSaved: 5,
    });
    res.json(approval);
  } catch (err) { res.status(500).json({ message: err.message }); }
});

router.patch('/:id/reject', async (req, res) => {
  try {
    const approval = await Approval.findOneAndUpdate(
      { _id: req.params.id, userId: req.user._id },
      { status: 'rejected', resolvedAt: new Date() },
      { new: true }
    );
    if (!approval) return res.status(404).json({ message: 'Not found' });
    await Activity.create({
      userId:      req.user._id,
      agentName:   approval.agentName,
      action:      approval.actionType,
      description: `Rejected: ${approval.title}`,
      status:      'rejected',
      minutesSaved: 0,
    });
    res.json(approval);
  } catch (err) { res.status(500).json({ message: err.message }); }
});

router.delete('/:id', async (req, res) => {
  try {
    const approval = await Approval.findOneAndUpdate(
      { _id: req.params.id, userId: req.user._id },
      { status: 'dismissed', resolvedAt: new Date() },
      { new: true }
    );
    if (!approval) return res.status(404).json({ message: 'Not found' });
    res.json({ success: true });
  } catch (err) { res.status(500).json({ message: err.message }); }
});

export default router;
