import mongoose from 'mongoose';

const notificationSchema = new mongoose.Schema({
  userId:    { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  title:     { type: String, required: true },
  body:      { type: String, default: '' },
  source:    { type: String, default: 'system' }, // agent name or source
  severity:  { type: String, enum: ['low', 'medium', 'high', 'critical'], default: 'medium' },
  dismissed: { type: Boolean, default: false },
  link:      { type: String, default: '' },
  createdAt: { type: Date, default: Date.now },
});

export default mongoose.model('Notification', notificationSchema);
