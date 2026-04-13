import mongoose from 'mongoose';

const financeSchema = new mongoose.Schema({
  userId:    { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  agentName: { type: String, default: 'FinanceAgent' },
  category:  { type: String, required: true }, // 'API Cost', 'Infra', 'SaaS Tools', etc.
  provider:  { type: String, default: '' },     // 'gemini', 'openai', 'anthropic', 'groq'
  model:     { type: String, default: '' },
  amount:    { type: Number, required: true },  // USD
  type:      { type: String, enum: ['expense', 'budget', 'saving'], default: 'expense' },
  inputTokens:  { type: Number, default: 0 },
  outputTokens: { type: Number, default: 0 },
  description:  { type: String, default: '' },
  date:      { type: Date, default: Date.now },
});

export default mongoose.model('Finance', financeSchema);
