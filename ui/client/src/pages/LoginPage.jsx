import { useState } from 'react';
import { useAuth } from '../context/AuthContext.jsx';
import { useNavigate } from 'react-router-dom';
import { Bot, Eye, EyeOff, AlertCircle, Loader2 } from 'lucide-react';

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode,     setMode]     = useState('login');  // 'login' | 'register'
  const [form,     setForm]     = useState({ name: '', email: '', password: '' });
  const [showPass, setShowPass] = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'login') {
        await login(form.email, form.password);
      } else {
        if (!form.name.trim()) { setError('Name is required'); setLoading(false); return; }
        await register(form.name, form.email, form.password);
      }
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen bg-bg-primary flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-accent-indigo/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 left-1/3 w-[400px] h-[300px] bg-accent-purple/5 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-sm animate-slide-up">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-accent-indigo flex items-center justify-center mx-auto mb-4 shadow-glow">
            <Bot size={22} className="text-white" />
          </div>
          <h1 className="text-2xl font-semibold text-text-primary">myOS</h1>
          <p className="text-sm text-text-muted mt-1">Personal AI Command Center</p>
        </div>

        {/* Card */}
        <div className="card p-6 space-y-5">
          {/* Mode toggle */}
          <div className="flex bg-bg-hover rounded-lg p-1">
            {['login', 'register'].map(m => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(''); }}
                className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-all duration-200 ${
                  mode === m ? 'bg-bg-card text-text-primary shadow-sm' : 'text-text-muted hover:text-text-secondary'
                }`}
              >
                {m === 'login' ? 'Sign In' : 'Create Account'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            {mode === 'register' && (
              <div>
                <label className="block text-xs text-text-secondary mb-1.5">Full Name</label>
                <input
                  id="login-name"
                  type="text"
                  className="input"
                  placeholder="Golan Levi"
                  value={form.name}
                  onChange={set('name')}
                  required={mode === 'register'}
                />
              </div>
            )}
            <div>
              <label className="block text-xs text-text-secondary mb-1.5">Email</label>
              <input
                id="login-email"
                type="email"
                className="input"
                placeholder="golan@myos.dev"
                value={form.email}
                onChange={set('email')}
                required
                autoComplete="email"
              />
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1.5">Password</label>
              <div className="relative">
                <input
                  id="login-password"
                  type={showPass ? 'text' : 'password'}
                  className="input pr-9"
                  placeholder="••••••••"
                  value={form.password}
                  onChange={set('password')}
                  required
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                />
                <button
                  type="button"
                  onClick={() => setShowPass(s => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary transition-colors"
                >
                  {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-accent-red/10 border border-accent-red/20">
                <AlertCircle size={13} className="text-accent-red flex-shrink-0" />
                <p className="text-xs text-accent-red">{error}</p>
              </div>
            )}

            <button
              id="login-submit"
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-accent-indigo text-white text-sm font-medium
                         hover:bg-indigo-400 transition-colors duration-150 disabled:opacity-50
                         flex items-center justify-center gap-2"
            >
              {loading ? (
                <><Loader2 size={14} className="animate-spin" /> Authenticating...</>
              ) : (
                mode === 'login' ? 'Sign In' : 'Create Account'
              )}
            </button>
          </form>

          {mode === 'login' && (
            <div className="pt-2 border-t border-border">
              <p className="text-center text-[11px] text-text-muted">
                Demo: <span className="text-text-secondary font-mono">golan@myos.dev</span> /{' '}
                <span className="text-text-secondary font-mono">password123</span>
              </p>
            </div>
          )}
        </div>

        <p className="text-center text-[11px] text-text-muted mt-5">
          Privacy-first · Self-hosted · Powered by LangGraph
        </p>
      </div>
    </div>
  );
}
