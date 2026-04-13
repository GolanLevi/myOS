import mongoose from 'mongoose';

const integrationSchema = new mongoose.Schema({
  userId:      { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  service:     { type: String, required: true },  // 'gmail', 'google_calendar', 'twitter', etc.
  category:    { type: String, required: true },  // 'google', 'social', 'finance', 'productivity'
  displayName: { type: String, required: true },
  description: { type: String, default: '' },
  icon:        { type: String, default: '' },
  status:      { type: String, enum: ['connected', 'disconnected', 'error'], default: 'disconnected' },
  accessToken: { type: String, default: '' },     // encrypted in production
  refreshToken:{ type: String, default: '' },
  lastSync:    { type: Date, default: null },
  syncInterval:{ type: Number, default: 15 },     // minutes
  metadata:    { type: mongoose.Schema.Types.Mixed, default: {} },
  connectedAt: { type: Date, default: null },
  createdAt:   { type: Date, default: Date.now },
});

export default mongoose.model('Integration', integrationSchema);
