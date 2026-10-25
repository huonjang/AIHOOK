
import { NavLink, Outlet } from "react-router-dom";
import { LayoutDashboard, FileText, ShieldAlert, Zap } from "lucide-react";

const navigation = [
  { to: "/", label: "Tổng quan", icon: LayoutDashboard, end: true },
  { to: "/invoices", label: "Hóa đơn", icon: FileText },
  { to: "/analytics", label: "Phân tích" },
  { to: "/alerts", label: "Cảnh báo", icon: ShieldAlert },
];

export default function MainLayout() {
  return (
    <div className="min-h-screen bg-slate-50 md:flex">
      <aside className="w-full bg-slate-950 p-5 text-white md:fixed md:inset-y-0 md:w-64">
        <div className="mb-8 flex items-center gap-3">
          <div className="rounded-xl bg-indigo-500 p-2">
            <Zap size={22} />
          </div>
          <div>
            <h1 className="text-xl font-bold">AITHOOK</h1>
            <p className="text-xs text-slate-400">Smart Invoice Insights</p>
          </div>
        </div>

        <nav className="flex flex-wrap gap-2 md:flex-col">
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-4 py-3 text-sm ${
                  isActive
                    ? "bg-indigo-500 text-white"
                    : "text-slate-300 hover:bg-slate-800"
                }`
              }
            >
              {Icon && <Icon size={19} />}
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-8 rounded-xl border border-slate-800 p-4">
          <p className="text-sm font-medium">Smart invoice insights</p>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Quản lý hóa đơn và nhận diện dấu hiệu bất thường.
          </p>
        </div>
      </aside>

      <main className="min-w-0 flex-1 p-5 md:ml-64 md:p-8 lg:p-10">
        <Outlet />
      </main>
    </div>
  );
}
