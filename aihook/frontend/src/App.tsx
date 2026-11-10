import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import DashboardPage from './pages/DashboardPage'
import InvoicesWorkspacePage from './pages/InvoicesWorkspacePage'
import AIAssistantPage from './pages/AIAssistantPage'

export default function App() {
  return <BrowserRouter><Routes><Route element={<MainLayout />}>
    <Route index element={<DashboardPage />} />
    <Route path="invoices" element={<InvoicesWorkspacePage />} />
    <Route path="ai" element={<AIAssistantPage />} />
    <Route path="analytics" element={<Navigate to="/ai" replace />} />
    <Route path="alerts" element={<Navigate to="/ai" replace />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Route></Routes></BrowserRouter>
}
