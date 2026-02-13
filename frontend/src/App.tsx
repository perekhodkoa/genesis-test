import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { ModelProvider } from './hooks/useModel';
import Layout from './components/Layout';
import AuthPage from './pages/AuthPage';
import ChatPage from './pages/ChatPage';
import UploadPage from './pages/UploadPage';
import BrowsePage from './pages/BrowsePage';
import InvitesPage from './pages/InvitesPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="app-loading">Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="app-loading">Loading...</div>;
  }

  if (user) {
    return <Navigate to="/chat" replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<PublicRoute><AuthPage /></PublicRoute>} />
          <Route element={<ProtectedRoute><ModelProvider><Layout /></ModelProvider></ProtectedRoute>}>
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/chat/:sessionId" element={<ChatPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/browse" element={<BrowsePage />} />
            <Route path="/invites" element={<InvitesPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
