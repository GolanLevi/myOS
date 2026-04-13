import { useState } from 'react';
import { useApi, useMutation } from '../hooks/useApi.js';
import { cn } from '../lib/utils.js';
import { CheckSquare, Plus, Check, Trash2, Loader2 } from 'lucide-react';

const PRIORITY_STYLES = {
  urgent: 'bg-accent-red/10    text-accent-red    border-accent-red/20',
  high:   'bg-accent-amber/10  text-accent-amber  border-accent-amber/20',
  medium: 'bg-accent-indigo/10 text-accent-indigo border-accent-indigo/20',
  low:    'bg-bg-hover          text-text-muted    border-border',
};

const STATUS_STYLES = {
  done:    'line-through text-text-muted',
  running: 'text-accent-blue',
  paused:  'text-accent-amber',
  failed:  'text-accent-red',
  pending: 'text-text-primary',
};

export default function TasksPage() {
  const { data: tasks, loading, refresh, setData } = useApi('/api/tasks');
  const { mutate: updateTask } = useMutation('patch', '/api/tasks');
  const { mutate: createTask } = useMutation('post', '/api/tasks');
  const { mutate: deleteTask } = useMutation('delete', '/api/tasks');

  const [newTitle, setNewTitle] = useState('');
  const [adding,   setAdding]   = useState(false);
  const [busy,     setBusy]     = useState(null);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    setAdding(true);
    try {
      const task = await createTask({ title: newTitle, priority: 'medium' }, '');
      setData(prev => prev ? [task, ...prev] : [task]);
      setNewTitle('');
    } finally { setAdding(false); }
  };

  const handleToggle = async (task) => {
    setBusy(task._id);
    const newStatus = task.status === 'done' ? 'pending' : 'done';
    try {
      const updated = await updateTask({ status: newStatus }, `/${task._id}`);
      setData(prev => prev?.map(t => t._id === task._id ? updated : t));
    } finally { setBusy(null); }
  };

  const handleDelete = async (id) => {
    setBusy(id);
    try {
      await deleteTask({}, `/${id}`);
      setData(prev => prev?.filter(t => t._id !== id));
    } finally { setBusy(null); }
  };

  const grouped = {
    running: tasks?.filter(t => t.status === 'running') || [],
    pending: tasks?.filter(t => t.status === 'pending') || [],
    paused:  tasks?.filter(t => t.status === 'paused')  || [],
    done:    tasks?.filter(t => t.status === 'done')    || [],
  };

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h1 className="text-2xl font-semibold text-text-primary">Tasks</h1>
        <p className="text-sm text-text-muted mt-0.5">
          {tasks?.filter(t => t.status !== 'done').length || 0} open tasks
        </p>
      </div>

      {/* Add task */}
      <form onSubmit={handleAdd} className="card p-3 flex items-center gap-2">
        <Plus size={14} className="text-text-muted flex-shrink-0" />
        <input
          value={newTitle}
          onChange={e => setNewTitle(e.target.value)}
          placeholder="Add a new task..."
          className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-muted focus:outline-none"
        />
        <button type="submit" disabled={adding || !newTitle.trim()} className="btn-primary h-7">
          {adding ? <Loader2 size={11} className="animate-spin" /> : 'Add'}
        </button>
      </form>

      {loading ? (
        <div className="space-y-2">{[1,2,3,4,5].map(i => <div key={i} className="card p-4 animate-pulse h-12" />)}</div>
      ) : (
        <div className="space-y-5">
          {Object.entries(grouped).map(([status, list]) => !list.length ? null : (
            <section key={status}>
              <h3 className={cn('section-title mb-2 capitalize',
                status === 'running' ? 'text-accent-blue'
                : status === 'done'  ? 'text-text-muted'
                : ''
              )}>
                {status} ({list.length})
              </h3>
              <div className="space-y-1.5">
                {list.map(task => (
                  <div key={task._id} className="card-hover px-3.5 py-2.5 flex items-center gap-3 group animate-fade-in">
                    <button
                      onClick={() => handleToggle(task)}
                      disabled={busy === task._id}
                      className={cn(
                        'w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-all',
                        task.status === 'done'
                          ? 'bg-accent-indigo border-accent-indigo'
                          : 'border-border hover:border-accent-indigo'
                      )}
                    >
                      {busy === task._id
                        ? <Loader2 size={10} className="animate-spin text-text-muted" />
                        : task.status === 'done'
                        ? <Check size={10} className="text-white" />
                        : null}
                    </button>
                    <div className="flex-1 min-w-0">
                      <p className={cn('text-sm transition-all', STATUS_STYLES[task.status])}>
                        {task.title}
                      </p>
                      <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                        <span className={cn('text-[10px] font-semibold px-1.5 py-0.5 rounded border capitalize', PRIORITY_STYLES[task.priority])}>
                          {task.priority}
                        </span>
                        {task.agentName && (
                          <span className="text-[10px] text-text-muted">{task.agentName}</span>
                        )}
                        {task.tags?.map(tag => (
                          <span key={tag} className="text-[10px] text-text-muted">#{tag}</span>
                        ))}
                      </div>
                    </div>
                    <button
                      onClick={() => handleDelete(task._id)}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-bg-card transition-all"
                    >
                      <Trash2 size={12} className="text-text-muted hover:text-accent-red transition-colors" />
                    </button>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
