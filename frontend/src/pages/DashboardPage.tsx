
import { useEffect, useState } from "react";
import {
  FileText,
  TrendingUp,
  TrendingDown,
  ShieldAlert,
  CalendarDays,
  RotateCcw,
  Search,
} from "lucide-react";

import StatCard from "../components/StatCard";
import { api, type Invoice } from "../services/api";

type DateMode = "all" | "custom";

const formatVND = (amount: string | number) => {
  const value = Number(amount);

  if (!Number.isFinite(value)) return "Không hợp lệ";

  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
    maximumFractionDigits: 0,
  }).format(value);
};

const getDatePart = (value: string) => value.slice(0, 10);

export default function DashboardPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [totalCost, setTotalCost] = useState<string | null>(null);
  const [confirmedCount, setConfirmedCount] = useState<number | null>(null);

  const [dateMode, setDateMode] = useState<DateMode>("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [appliedStartDate, setAppliedStartDate] = useState("");
  const [appliedEndDate, setAppliedEndDate] = useState("");

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDashboard = async (
    start?: string,
    end?: string,
  ) => {
    setIsLoading(true);
    setError("");

    try {
      const [invoiceList, summary] = await Promise.all([
        api.getInvoices(),
        start && end
          ? api.getInvoiceSummary(start, end)
          : api.getInvoiceSummaryAll(),
      ]);

      setInvoices(invoiceList);
      setTotalCost(summary.total_amount);
      setConfirmedCount(summary.invoice_count);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Không thể tải dữ liệu Dashboard.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadDashboard();

    // Chỉ tải dữ liệu khi Dashboard được mở.
    // Bộ lọc được áp dụng bằng nút bên dưới.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredInvoices =
    dateMode === "all" || !appliedStartDate || !appliedEndDate
      ? invoices
      : invoices.filter((invoice) => {
          const uploadDate = getDatePart(invoice.created_at);

          return (
            uploadDate >= appliedStartDate &&
            uploadDate <= appliedEndDate
          );
        });

  const applyDateFilter = async () => {
    if (dateMode === "custom") {
      if (!startDate || !endDate) {
        setError("Vui lòng chọn cả ngày bắt đầu và ngày kết thúc.");
        return;
      }

      if (startDate > endDate) {
        setError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.");
        return;
      }

      setAppliedStartDate(startDate);
      setAppliedEndDate(endDate);
      await loadDashboard(startDate, endDate);
      return;
    }

    setAppliedStartDate("");
    setAppliedEndDate("");
    await loadDashboard();
  };

  const resetDateFilter = async () => {
    setDateMode("all");
    setStartDate("");
    setEndDate("");
    setAppliedStartDate("");
    setAppliedEndDate("");
    await loadDashboard();
  };

  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm text-slate-500">
          AITHOOK / Workspace
        </p>

        <h2 className="mt-2 text-3xl font-bold text-slate-900">
          Tổng quan
        </h2>

        <p className="mt-2 text-sm text-slate-500">
          Theo dõi tình hình hóa đơn và các dấu hiệu bất thường.
        </p>
      </header>

      {/* Bộ lọc thời gian */}
      <section className="rounded-2xl border border-[#E7E1F3] bg-white p-4 shadow-sm sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-[#F0EDFA]">
              <CalendarDays size={20} className="text-[#7567BC]" />
            </div>

            <div>
              <h3 className="font-semibold text-[#302B4A]">
                Khoảng thời gian
              </h3>
              <p className="mt-1 text-sm text-[#817B9D]">
                Chọn thời gian để xem số liệu chi tiết.
              </p>
            </div>
          </div>

          <span className="rounded-full bg-[#F0EDFA] px-3 py-1.5 text-xs font-medium text-[#7567BC]">
            {dateMode === "all"
              ? "Toàn bộ thời gian"
              : "Khoảng thời gian tùy chỉnh"}
          </span>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setDateMode("all")}
            className={`rounded-xl border px-4 py-2 text-sm font-medium transition-colors ${
              dateMode === "all"
                ? "border-[#8C7BEF] bg-[#F0EDFA] text-[#6454B5]"
                : "border-[#E7E3F0] text-[#514B65] hover:bg-[#FBFAFE]"
            }`}
          >
            Toàn bộ thời gian
          </button>

          <button
            type="button"
            onClick={() => setDateMode("custom")}
            className={`rounded-xl border px-4 py-2 text-sm font-medium transition-colors ${
              dateMode === "custom"
                ? "border-[#8C7BEF] bg-[#F0EDFA] text-[#6454B5]"
                : "border-[#E7E3F0] text-[#514B65] hover:bg-[#FBFAFE]"
            }`}
          >
            Tùy chỉnh ngày
          </button>
        </div>

        {dateMode === "custom" && (
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label
                htmlFor="dashboard-start-date"
                className="mb-1.5 block text-sm font-medium text-[#514B65]"
              >
                Từ ngày
              </label>

              <input
                id="dashboard-start-date"
                type="date"
                value={startDate}
                max={endDate || undefined}
                onChange={(event) => setStartDate(event.target.value)}
                className="w-full rounded-xl border border-[#E7E3F0] bg-white px-3 py-2.5 text-sm text-[#302B4A] outline-none transition focus:border-[#8C7BEF] focus:ring-2 focus:ring-[#8C7BEF]/20"
              />
            </div>

            <div>
              <label
                htmlFor="dashboard-end-date"
                className="mb-1.5 block text-sm font-medium text-[#514B65]"
              >
                Đến ngày
              </label>

              <input
                id="dashboard-end-date"
                type="date"
                value={endDate}
                min={startDate || undefined}
                onChange={(event) => setEndDate(event.target.value)}
                className="w-full rounded-xl border border-[#E7E3F0] bg-white px-3 py-2.5 text-sm text-[#302B4A] outline-none transition focus:border-[#8C7BEF] focus:ring-2 focus:ring-[#8C7BEF]/20"
              />
            </div>
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void applyDateFilter()}
            disabled={isLoading}
            className="inline-flex items-center gap-2 rounded-xl bg-[#8C7BEF] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#7967E5] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Search size={16} />
            {isLoading ? "Đang tải..." : "Áp dụng"}
          </button>

          <button
            type="button"
            onClick={() => void resetDateFilter()}
            disabled={isLoading}
            className="inline-flex items-center gap-2 rounded-xl border border-[#E7E3F0] px-4 py-2.5 text-sm font-medium text-[#514B65] transition-colors hover:bg-[#FBFAFE] disabled:opacity-60"
          >
            <RotateCcw size={16} />
            Đặt lại
          </button>
        </div>

        {appliedStartDate && appliedEndDate && (
          <p className="mt-3 text-sm text-[#7567BC]">
            Đang xem từ {appliedStartDate} đến {appliedEndDate}.
          </p>
        )}
      </section>

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          Không thể cập nhật Dashboard: {error}
        </div>
      )}

      {/* Thẻ thống kê */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Tổng hóa đơn"
          value={
            isLoading
              ? "..."
              : filteredInvoices.length.toLocaleString("vi-VN")
          }
          note={
            dateMode === "all"
              ? "Toàn bộ hóa đơn đã tải lên"
              : "Lọc theo ngày tải lên"
          }
          icon={FileText}
        />

        <StatCard
          title="Tổng chi phí"
          value={
            isLoading
              ? "..."
              : totalCost === null
                ? "N/A"
                : formatVND(totalCost)
          }
          note={
            dateMode === "all"
              ? "Hóa đơn đã xác nhận, mọi thời điểm"
              : "Hóa đơn đã xác nhận, theo ngày lập"
          }
          icon={TrendingUp}
        />

        <StatCard
          title="Đã xử lý"
          value="—"
          note="Chưa có quy tắc thống kê thống nhất"
          icon={TrendingDown}
        />

        <StatCard
          title="Cảnh báo"
          value="—"
          note="Chưa kết nối API cảnh báo"
          icon={ShieldAlert}
        />
      </div>

      {/* Phần chi tiết bổ sung */}
      <section className="rounded-2xl border border-[#E7E1F3] bg-white p-4 shadow-sm sm:p-5">
        <div>
          <h3 className="text-lg font-semibold text-[#302B4A]">
            Chi tiết thống kê
          </h3>
          <p className="mt-1 text-sm text-[#817B9D]">
            Tổng hợp theo bộ lọc đang áp dụng.
          </p>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl bg-[#F8F6FD] p-4">
            <p className="text-sm text-[#817B9D]">
              Số hóa đơn đã tải lên
            </p>
            <p className="mt-2 text-2xl font-semibold text-[#302B4A]">
              {isLoading
                ? "..."
                : filteredInvoices.length.toLocaleString("vi-VN")}
            </p>
          </div>

          <div className="rounded-xl bg-[#F8F6FD] p-4">
            <p className="text-sm text-[#817B9D]">
              Số hóa đơn đã xác nhận
            </p>
            <p className="mt-2 text-2xl font-semibold text-[#302B4A]">
              {isLoading
                ? "..."
                : confirmedCount === null
                  ? "N/A"
                  : confirmedCount.toLocaleString("vi-VN")}
            </p>
          </div>
        </div>

        <p className="mt-4 text-xs leading-5 text-[#817B9D]">
          Số hóa đơn đã tải lên được lọc theo thời điểm tải tệp.
          Tổng chi phí và số hóa đơn đã xác nhận được tính theo ngày
          lập hóa đơn. Hai nhóm số liệu có thể khác nhau nếu hóa đơn
          chưa được OCR hoặc chưa được xác nhận.
        </p>
      </section>
    </div>
  );
}
