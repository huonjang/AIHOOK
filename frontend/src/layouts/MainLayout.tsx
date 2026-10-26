import { NavLink, Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  FileText,
  ShieldAlert,
  Zap,
} from "lucide-react";

const navigation = [
  { to: "/", label: "Tổng quan", icon: LayoutDashboard, end: true },
  { to: "/invoices", label: "Hóa đơn", icon: FileText },
  { to: "/analytics", label: "Phân tích" },
  { to: "/alerts", label: "Cảnh báo", icon: ShieldAlert },
];

export default function MainLayout() {
  return (
    <div className="min-h-screen bg-[#F7F6FC] text-[#302B4A] md:flex">
      <aside className="w-full border-b border-[#E7E2F2] bg-[#F0EDFA] p-5 md:fixed md:inset-y-0 md:w-64 md:overflow-y-auto md:border-b-0 md:border-r">
        {/* Logo */}
        <div className="mb-8 flex items-center gap-3">
          <div className="rounded-xl bg-[#8B80E8] p-2 text-white shadow-sm">
            <Zap size={22} />
          </div>

          <div>
            <h1 className="text-xl font-bold tracking-tight text-[#302B4A]">
              AITHOOK
            </h1>
            <p className="text-xs text-[#817B9D]">
              Smart Invoice Insights
            </p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex flex-wrap gap-2 md:flex-col">
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-colors duration-200 ${
                  isActive
                    ? "bg-[#E1DAFF] text-[#594B9D] shadow-sm"
                    : "text-[#716B8B] hover:bg-[#E8E3F6] hover:text-[#302B4A]"
                }`
              }
            >
              {Icon && <Icon size={19} />}
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Description */}
        <div className="mt-8 rounded-xl border border-[#E1DBEF] bg-white/60 p-4">
          <p className="text-sm font-semibold text-[#484064]">
            Smart invoice insights
          </p>
          <p className="mt-1 text-xs leading-5 text-[#817B9D]">
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