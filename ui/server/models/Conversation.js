import mongoose from 'mongoose';

const messageSchema = new mongoose.Schema({
  role:      { type: String, enum: ['user', 'assistant'], required: true },
  content:   { type: String, required: true },
  createdAt: { type: Date, default: Date.now },
});

const conversationSchema = new mongoose.Schema({
  userId:       { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  title:        { type: String, default: 'New conversation' },
  messages:     [messageSchema],
  lastActivity: { type: Date, default: Date.now },
  createdAt:    { type: Date, default: Date.now },
});

// Auto-delete conversations after 7 days of inactivity
conversationSchema.index({ lastActivity: 1 }, { expireAfterSeconds: 60 * 60 * 24 * 7 });

export default mongoose.model('Conversation', conversationSchema);
