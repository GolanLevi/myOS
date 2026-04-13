import mongoose from 'mongoose';

const agentSchema = new mongoose.Schema({
  userId:      { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  name:        { type: String, required: true },
  type:        { type: String, required: true }, // e.g. 'SecretariatAgent', 'FinanceAgent'
  description: { type: String, default: '' },
  status:      { type: String, enum: ['active', 'paused', 'error', 'idle'], default: 'idle' },
  color:       { type: String, default: '#6366f1' },
  lastAction:  { type: String, default: '' },
  lastRun:     { type: Date, default: null },
  nextRun:     { type: Date, default: null },
  actionsToday:{ type: Number, default: 0 },
  totalActions:{ type: Number, default: 0 },
  costToday:   { type: Number, default: 0 },
  createdAt:   { type: Date, default: Date.now },
});

export default mongoose.model('Agent', agentSchema);
