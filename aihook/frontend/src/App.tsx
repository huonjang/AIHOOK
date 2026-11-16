import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import DashboardPage from './pages/DashboardPage'
import InvoicesWorkspacePage from './pages/InvoicesWorkspacePage'
import AIAssistantPage from './pages/AIAssistantPage'
import AccountPage from './pages/AccountPage'
import AuthPage from './pages/AuthPage'
import { AuthProvider, useAuth } from './auth/AuthContext'

function ProtectedApp() {
  const { profile, loading, onAuthenticated } = useAuth()
  if (loading) return <div className="app-shell grid min-h-screen place-items-center text-[#aad6eb]">Đang xác thực phiên đăng nhập...</div>
  if (!profile) return <AuthPage onAuthenticated={onAuthenticated} />
  return <BrowserRouter><Routes><Route element={<MainLayout />}>
    <Route index element={<DashboardPage />} />
    <Route path="invoices" element={<InvoicesWorkspacePage />} />
    <Route path="ai" element={<AIAssistantPage />} />
    <Route path="account" element={<AccountPage />} />
    <Route path="analytics" element={<Navigate to="/ai" replace />} />
    <Route path="alerts" element={<Navigate to="/ai" replace />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Route></Routes></BrowserRouter>
}

export default function App() {
  return <AuthProvider><ProtectedApp /></AuthProvider>
}
