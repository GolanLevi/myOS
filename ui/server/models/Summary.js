import mongoose from 'mongoose';

const summarySchema = new mongoose.Schema({
  userId:    { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  agentName: { type: String, required: true },
  source:    { type: String, required: true }, // 'gmail', 'linkedin', 'twitter', 'system'
  title:     { type: String, required: true },
  content:   { type: String, required: true },
  sentiment: { type: String, enum: ['positive', 'neutral', 'negative'], default: 'neutral' },
  tags:      [{ type: String }],
  read:      { type: Boolean, default: false },
  priority:  { type: String, enum: ['low', 'medium', 'high'], default: 'medium' },
  createdAt: { type: Date, default: Date.now },
});

export default mongoose.model('Summary', summarySchema);
