import mongoose from 'mongoose';

const taskSchema = new mongoose.Schema({
  userId:     { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  agentName:  { type: String, default: '' },
  title:      { type: String, required: true },
  description:{ type: String, default: '' },
  status:     { type: String, enum: ['pending', 'running', 'done', 'failed', 'paused'], default: 'pending' },
  priority:   { type: String, enum: ['low', 'medium', 'high', 'urgent'], default: 'medium' },
  tags:       [{ type: String }],
  dueDate:    { type: Date, default: null },
  completedAt:{ type: Date, default: null },
  createdAt:  { type: Date, default: Date.now },
});

export default mongoose.model('Task', taskSchema);
