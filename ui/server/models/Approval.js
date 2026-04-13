import mongoose from 'mongoose';

const approvalSchema = new mongoose.Schema({
  userId:     { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  agentName:  { type: String, required: true },
  actionType: { type: String, required: true }, // 'send_email', 'create_event', etc.
  title:      { type: String, required: true },
  description:{ type: String, default: '' },
  senderName: { type: String, default: '' },
  senderEmail:{ type: String, default: '' },
  payload:    { type: mongoose.Schema.Types.Mixed, default: {} },
  status:     { type: String, enum: ['pending', 'approved', 'rejected', 'dismissed'], default: 'pending' },
  confidence: { type: Number, min: 0, max: 100, default: 85 },
  threadId:   { type: String, default: '' }, // LangGraph thread_id for resuming
  resolvedAt: { type: Date, default: null },
  createdAt:  { type: Date, default: Date.now },
});

export default mongoose.model('Approval', approvalSchema);
