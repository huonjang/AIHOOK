
import {
  FileText,
  TrendingUp,
  TrendingDown,
  ShieldAlert,
} from "lucide-react";

import StatCard from "../components/StatCard";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm text-slate-500">AITHOOK / Workspace</p>
        <h2 className="mt-2 text-3xl font-bold text-slate-900">
          Tổng quan
        </h2>
        <p className="mt-2 text-sm text-slate-500">
          Theo dõi tình hình hóa đơn và các dấu hiệu bất thường.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Tổng hóa đơn"
          value="128"
          note="Dữ liệu minh họa"
          icon={FileText}
        />
        <StatCard
          title="Tổng chi phí"
          value="85,4 triệu"
          note="Dữ liệu minh họa"
          icon={TrendingUp}
        />
        <StatCard
          title="Đã xử lý"
          value="96"
          note="Dữ liệu minh họa"
          icon={TrendingDown}
        />
        <StatCard
          title="Cảnh báo"
          value="7"
          note="Cần kiểm tra"
          icon={ShieldAlert}
        />
      </div>
    </div>
  );
}
