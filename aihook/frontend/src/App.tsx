
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import MainLayout from "./layouts/MainLayout";
import DashboardPage from "./pages/DashboardPage";
import InvoicesPage from "./pages/InvoicesPage";
import AnalyticsPage from "./pages/AnalyticsPage";


export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<MainLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="invoices" element={<InvoicesPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="alerts" element={<Navigate to="/analytics" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
