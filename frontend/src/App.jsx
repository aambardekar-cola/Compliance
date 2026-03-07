import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthSession } from './auth/AuthProvider';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Regulations from './pages/Regulations';
import RegulationDetail from './pages/RegulationDetail';
import GapAnalysis from './pages/GapAnalysis';
import Communications from './pages/Communications';
import ExecSummary from './pages/ExecSummary';
import Settings from './pages/Settings';
import AdminUrls from './pages/AdminUrls';

function ProtectedRoute({ children }) {
  const { isAuthenticated, isSessionLoading } = useAuthSession();

  if (isSessionLoading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner" />
        <p>Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <Layout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/regulations" element={<Regulations />} />
                <Route path="/regulations/:id" element={<RegulationDetail />} />
                <Route path="/gaps" element={<GapAnalysis />} />
                <Route path="/communications" element={<Communications />} />
                <Route path="/reports" element={<ExecSummary />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/admin/urls" element={<AdminUrls />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

export default App;
