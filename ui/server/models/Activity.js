import mongoose from 'mongoose';

const activitySchema = new mongoose.Schema({
  userId:     { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  agentName:  { type: String, required: true },
  action:     { type: String, required: true },     // 'send_email', 'create_event', etc.
  description:{ type: String, required: true },
  status:     { type: String, enum: ['success', 'pending', 'failed', 'approved', 'rejected'], default: 'success' },
  minutesSaved:{ type: Number, default: 0 },
  metadata:   { type: mongoose.Schema.Types.Mixed, default: {} },
  createdAt:  { type: Date, default: Date.now },
});

export default mongoose.model('Activity', activitySchema);
