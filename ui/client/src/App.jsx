import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext.jsx';
import AppLayout        from './components/layout/AppLayout.jsx';
import LoginPage        from './pages/LoginPage.jsx';
import TodayPage        from './pages/TodayPage.jsx';
import InboxPage        from './pages/InboxPage.jsx';
import ApprovalsPage    from './pages/ApprovalsPage.jsx';
import TasksPage        from './pages/TasksPage.jsx';
import TimelinePage     from './pages/TimelinePage.jsx';
import CostPage         from './pages/CostPage.jsx';
import AdminPage        from './pages/AdminPage.jsx';
import IntegrationsPage from './pages/IntegrationsPage.jsx';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return (
    <div className="flex h-screen items-center justify-center bg-bg-primary">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 rounded-full border-2 border-accent-indigo border-t-transparent animate-spin" />
        <p className="text-text-muted text-sm">Loading myOS...</p>
      </div>
    </div>
  );
  return user ? children : <Navigate to="/login" replace />;
}

function AppRoutes() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route path="/" element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route index               element={<TodayPage />} />
        <Route path="inbox"        element={<InboxPage />} />
        <Route path="approvals"    element={<ApprovalsPage />} />
        <Route path="tasks"        element={<TasksPage />} />
        <Route path="timeline"     element={<TimelinePage />} />
        <Route path="cost"         element={<CostPage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="admin"        element={<AdminPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
