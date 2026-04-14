import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import { getVisibleInboxItems } from '../../lib/inboxFilters.js';
import {
  LayoutDashboard, Mail, CheckSquare, Clock, DollarSign,
  Settings, Plug, LogOut, Bot, Bell
} from 'lucide-react';
import { cn } from '../../lib/utils.js';

const NAV = [
  { to: '/',             label: 'Today',        icon: LayoutDashboard, exactEnd: true },
  { to: '/approvals',    label: 'Approvals',    icon: Bell,            badge: 'approvals' },
  { to: '/inbox',        label: 'Email Inbox',  icon: Mail,            badge: 'summaries' },
  { to: '/tasks',        label: 'Tasks',        icon: CheckSquare },
  { to: '/timeline',     label: 'Timeline',     icon: Clock },
  { to: '/cost',         label: 'Cost & Value', icon: DollarSign },
  { to: '/integrations', label: 'Connections',  icon: Plug },
  { to: '/admin',        label: 'Admin',        icon: Settings },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { data: approvals } = useApi('/api/approvals', { params: { status: 'pending' } });
  const { data: summaries } = useApi('/api/summaries', { params: { unread: 'true' } });
  const approvalItems = Array.isArray(approvals) ? approvals : [];
  const summaryItems = getVisibleInboxItems(Array.isArray(summaries) ? summaries : []);

  const counts = {
    approvals: approvalItems.length,
    summaries: summaryItems.filter((item) => !item.read && !item.isActionable).length,
  };

  const initials = user?.name?.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2) || 'GL';

  return (
    <aside className="w-[220px] flex-shrink-0 flex flex-col h-full bg-bg-secondary border-r border-border">
      <div className="px-4 py-5 flex items-center gap-2.5 border-b border-border">
        <div className="w-7 h-7 rounded-lg bg-accent-indigo flex items-center justify-center flex-shrink-0">
          <Bot size={14} className="text-white" />
        </div>
        <div>
          <span className="text-sm font-semibold text-text-primary tracking-tight">myOS</span>
          <p className="text-[10px] text-text-muted leading-none mt-0.5">Personal AI Command Center</p>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        {NAV.map(({ to, label, icon: Icon, badge, exactEnd }) => {
          const count = badge ? counts[badge] : 0;
          return (
            <NavLink
              key={to}
              to={to}
              end={exactEnd}
              className={({ isActive }) =>
                cn(
                  'group flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150',
                  isActive
                    ? 'bg-bg-active text-text-primary border-l-2 border-accent-indigo pl-[10px]'
                    : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary border-l-2 border-transparent pl-[10px]'
                )
              }
            >
              <Icon size={15} className="flex-shrink-0" />
              <span className="flex-1 font-medium">{label}</span>
              {count > 0 && (
                <span className="badge bg-accent-indigo text-white text-[10px] px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                  {count}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      <div className="border-t border-border p-3">
        <div
          className="flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-bg-hover transition-colors cursor-pointer group"
          onClick={() => navigate('/admin')}
        >
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent-indigo to-accent-purple flex items-center justify-center text-[11px] font-semibold text-white flex-shrink-0">
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-text-primary truncate">{user?.name || 'User'}</p>
            <p className="text-[10px] text-text-muted truncate">{user?.email || ''}</p>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); logout(); navigate('/login'); }}
            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-bg-card transition-all"
            title="Sign out"
          >
            <LogOut size={12} className="text-text-muted" />
          </button>
        </div>
      </div>
    </aside>
  );
}
