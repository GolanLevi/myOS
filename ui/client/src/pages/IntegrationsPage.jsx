import { useApi, useMutation } from '../hooks/useApi.js';
import { timeAgo, cn } from '../lib/utils.js';
import { Plug, CheckCircle2, XCircle, RefreshCw, Loader2 } from 'lucide-react';
import { useState } from 'react';

const CATEGORY_META = {
  google:       { label: 'Google',       color: 'text-accent-blue' },
  social:       { label: 'Social Media', color: 'text-accent-pink' },
  finance:      { label: 'Finance',      color: 'text-accent-green' },
  productivity: { label: 'Productivity', color: 'text-accent-indigo' },
};

export default function IntegrationsPage() {
  const { data: integrations, loading, refresh } = useApi('/api/integrations');
  const { mutate: connect }    = useMutation('post', '/api/integrations/connect');
  const { mutate: disconnect } = useMutation('post', '/api/integrations/disconnect');
  const [busy, setBusy] = useState(null);

  const handleToggle = async (integration) => {
    setBusy(integration._id);
    try {
      if (integration.status === 'connected') {
        await disconnect({ service: integration.service });
      } else {
        await connect({ service: integration.service });
      }
      refresh();
    } finally { setBusy(null); }
  };

  // Group by category
  const groups = {};
  integrations?.forEach(i => {
    if (!groups[i.category]) groups[i.category] = [];
    groups[i.category].push(i);
  });

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary">Connections</h1>
          <p className="text-sm text-text-muted mt-0.5">Connect external services to expand agent capabilities</p>
        </div>
        <button onClick={refresh} className="btn-ghost">
          <RefreshCw size={13} className={cn(loading && 'animate-spin')} />
        </button>
      </div>

      {/* Stats bar */}
      {integrations && (
        <div className="card p-3.5 flex items-center gap-6">
          <div>
            <span className="text-lg font-semibold text-accent-green">
              {integrations.filter(i => i.status === 'connected').length}
            </span>
            <span className="text-xs text-text-muted ml-1.5">connected</span>
          </div>
          <div className="w-px h-5 bg-border" />
          <div>
            <span className="text-lg font-semibold text-text-primary">{integrations.length}</span>
            <span className="text-xs text-text-muted ml-1.5">total available</span>
          </div>
          <div className="flex-1 h-1.5 bg-bg-hover rounded-full overflow-hidden">
            <div
              className="h-full bg-accent-green rounded-full transition-all duration-500"
              style={{ width: `${(integrations.filter(i => i.status === 'connected').length / integrations.length) * 100}%` }}
            />
          </div>
        </div>
      )}

      {loading ? (
        <div className="space-y-6">
          {[1,2,3].map(g => (
            <div key={g} className="space-y-2">
              <div className="h-3 bg-bg-hover rounded w-24 animate-pulse" />
              {[1,2,3].map(i => <div key={i} className="card p-4 animate-pulse h-16" />)}
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(groups).map(([category, items]) => {
            const catMeta = CATEGORY_META[category] || { label: category, color: 'text-text-muted' };
            return (
              <section key={category} className="space-y-2 animate-slide-up">
                <div className="flex items-center gap-2 mb-3">
                  <span className={cn('section-title', catMeta.color)}>{catMeta.label}</span>
                  <span className="text-[10px] text-text-muted">({items.filter(i => i.status === 'connected').length}/{items.length} connected)</span>
                </div>
                <div className="grid gap-2">
                  {items.map(integration => {
                    const isConnected = integration.status === 'connected';
                    const isBusy = busy === integration._id;
                    return (
                      <div key={integration._id} className="card-hover p-4 flex items-center gap-4">
                        {/* Status icon */}
                        <div className={cn(
                          'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
                          isConnected ? 'bg-accent-green/10' : 'bg-bg-hover'
                        )}>
                          <Plug size={15} className={isConnected ? 'text-accent-green' : 'text-text-muted'} />
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium text-text-primary">{integration.displayName}</p>
                            {isConnected
                              ? <CheckCircle2 size={12} className="text-accent-green" />
                              : <XCircle     size={12} className="text-text-muted" />}
                          </div>
                          <p className="text-[11px] text-text-muted mt-0.5">{integration.description}</p>
                          {isConnected && integration.lastSync && (
                            <p className="text-[10px] text-accent-green mt-0.5">
                              Last synced {timeAgo(integration.lastSync)}
                            </p>
                          )}
                        </div>

                        <div className="flex items-center gap-2 flex-shrink-0">
                          {isConnected && (
                            <div className="flex items-center gap-1.5 mr-1">
                              <div className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse-dot" />
                              <span className="text-[10px] text-accent-green font-medium">Live</span>
                            </div>
                          )}
                          <button
                            onClick={() => handleToggle(integration)}
                            disabled={isBusy}
                            className={cn(
                              'h-8 text-[11px]',
                              isConnected ? 'btn-secondary text-accent-red border-accent-red/20 hover:border-accent-red/40' : 'btn-primary'
                            )}
                          >
                            {isBusy
                              ? <Loader2 size={11} className="animate-spin" />
                              : isConnected ? 'Disconnect' : 'Connect'}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      )}

      {/* Info banner */}
      <div className="card p-4 border-accent-indigo/20 bg-accent-indigo/5">
        <p className="text-xs text-accent-indigo font-medium mb-1">🔌 Real OAuth Coming Soon</p>
        <p className="text-[11px] text-text-muted">
          Currently simulating connections. Real OAuth flows (Google, Plaid) will be wired in Phase 2.
          Gmail and Calendar are already connected via the main myOS Python backend.
        </p>
      </div>
    </div>
  );
}
