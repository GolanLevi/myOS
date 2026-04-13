import { Outlet } from 'react-router-dom';
import Sidebar    from './Sidebar.jsx';
import ChatPanel  from './ChatPanel.jsx';

export default function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-bg-primary">
      <Sidebar />
      <div className="flex flex-1 overflow-hidden">
        {/* Main scrollable content */}
        <main className="flex-1 overflow-y-auto">
          <div className="w-full px-6 py-6 max-w-[1180px] animate-fade-in">
            <Outlet />
          </div>
        </main>
        {/* Knowledge Agent chat panel (replaces static right panel) */}
        <ChatPanel />
      </div>
    </div>
  );
}
