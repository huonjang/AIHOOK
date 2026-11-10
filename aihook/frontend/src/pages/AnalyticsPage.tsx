import InvoiceChat from '../components/chat/InvoiceChat'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BarChart, Bar, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type AnalyticsDashboard } from '../services/api'

const money = (value: string | number) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 2 }).format(Number(value))
const panel = 'rounded-2xl border border-[#E7E1F3] bg-white p-5 shadow-sm'
const button = 'rounded-xl border border-[#E7E1F3] px-4 py-2 text-sm font-medium disabled:opacity-50'

export default function AnalyticsPage({ showAI = true }: { showAI?: boolean }) {
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [filter, setFilter] = useState({ start: '', end: '', revision: 0 })
  const [data, setData] = useState<AnalyticsDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filterError, setFilterError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    setData(null)
    api.getAnalytics(filter.start, filter.end, controller.signal)
      .then(result => { if (!controller.signal.aborted) setData(result) })
      .catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Không thể tải dữ liệu.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [filter])

  function apply() {
    if ((!start !== !end) || (start && start > end)) {
      setFilterError('Chọn đủ hai ngày; ngày bắt đầu phải trước hoặc bằng ngày kết thúc.')
      return
    }
    setFilterError('')
    setFilter({ start, end, revision: filter.revision + 1 })
  }

  const chart = data?.monthly.map(item => ({ ...item, amount: Number(item.total_amount) })) ?? []

  return <div className="space-y-6 text-[#302B4A]">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div><p className="text-sm text-[#817B9D]">Workspace / Phân tích</p>
        <h1 className="mt-2 text-3xl font-bold">{showAI ? 'Phân tích & AI' : 'Tổng quan hóa đơn'}</h1>
        <p className="mt-2 text-sm text-[#817B9D]">Giá trị hóa đơn đã ghi nhận, tổng hợp theo ngày lập hóa đơn.</p>
      </div>
      <button className={button} disabled={loading} onClick={() => setFilter({ ...filter, revision: filter.revision + 1 })}>Làm mới</button>
    </header>
    <section className={panel} aria-label="Bộ lọc thời gian">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-2 text-sm">Từ ngày<input type="date" value={start} onChange={e => setStart(e.target.value)} className="rounded-lg border border-[#E7E1F3] p-2" /></label>
        <label className="flex flex-col gap-2 text-sm">Đến ngày<input type="date" value={end} onChange={e => setEnd(e.target.value)} className="rounded-lg border border-[#E7E1F3] p-2" /></label>
        <button className={`${button} bg-[#8C7BEF] text-white`} onClick={apply}>Áp dụng</button>
        <button className={button} onClick={() => { setStart(''); setEnd(''); setFilterError(''); setFilter({ start: '', end: '', revision: filter.revision + 1 }) }}>Toàn bộ thời gian</button>
      </div>
      <p className="mt-3 text-sm text-[#817B9D]">Đang xem: {filter.start ? `${filter.start} đến ${filter.end}` : 'Toàn bộ thời gian'}. Bao gồm cả ngày đầu và ngày cuối.</p>
      {filterError && <p role="alert" className="mt-3 text-sm text-red-700">{filterError}</p>}
    </section>
    {showAI && <InvoiceChat key={`${filter.start}:${filter.end}`} start={filter.start} end={filter.end} />}
    {loading && <p role="status" className={panel}>Đang tải thống kê...</p>}
    {error && <div role="alert" className={`${panel} text-red-700`}>Không thể tải thống kê: {error} <button className={button} onClick={() => setFilter({ ...filter, revision: filter.revision + 1 })}>Thử lại</button></div>}
    {data && <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ['Tổng giá trị hóa đơn', money(data.overview.total_amount)],
          ['Hóa đơn đã ghi nhận', data.overview.invoice_count.toLocaleString('vi-VN')],
          ['Giá trị trung bình', money(data.overview.average_amount)],
          ['Đơn vị bán', data.overview.supplier_count.toLocaleString('vi-VN')],
        ].map(([label, value]) => <section key={label} className={panel}><p className="text-sm text-[#817B9D]">{label}</p><p className="mt-3 break-words text-2xl font-bold">{value}</p></section>)}
      </div>
      {data.overview.undated_count > 0 && <p className="rounded-xl bg-amber-50 p-4 text-sm text-amber-800">Có {data.overview.undated_count} hóa đơn đã ghi nhận thiếu ngày lập: được tính trong tổng toàn thời gian, nhưng không nằm trong biểu đồ tháng hoặc bộ lọc ngày.</p>}
      {data.overview.invoice_count === 0 ? <section className={`${panel} py-12 text-center`}><h2 className="text-lg font-semibold">Chưa có hóa đơn đã ghi nhận trong khoảng này</h2><p className="mt-2 text-sm text-[#817B9D]">Thử đổi khoảng ngày hoặc tải hóa đơn để hệ thống tự động xử lý.</p><Link to="/invoices" className="mt-4 inline-block text-[#7567BC] underline">Đi đến hóa đơn</Link></section> : <>
        <section className={panel}>
          <h2 className="text-lg font-semibold">Giá trị hóa đơn theo tháng</h2>
          <p className="mt-1 text-sm text-[#817B9D]">Đơn vị: VND · Tháng không có hóa đơn được hiển thị bằng 0.</p>
          <div className="mt-5 h-72 min-w-0">
            <ResponsiveContainer width="100%" height="100%"><BarChart data={chart} margin={{ left: 10, right: 10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="month" tick={{ fontSize: 12 }} /><YAxis width={70} tick={{ fontSize: 12 }} tickFormatter={v => new Intl.NumberFormat('vi-VN', { notation: 'compact' }).format(Number(v))} />
              <Tooltip formatter={value => money(Number(value))} /><Bar dataKey="amount" name="Giá trị hóa đơn" fill="#8C7BEF" radius={[5, 5, 0, 0]} />
            </BarChart></ResponsiveContainer>
          </div>
          <details className="mt-4 text-sm"><summary className="cursor-pointer text-[#7567BC]">Xem số liệu theo tháng</summary><div className="mt-3 overflow-x-auto"><table className="w-full text-left"><thead><tr><th className="p-2">Tháng</th><th>Số hóa đơn</th><th className="text-right">Giá trị</th></tr></thead><tbody>{data.monthly.map(row => <tr key={row.month} className="border-t border-[#EEEAF5]"><td className="p-2">{row.month}</td><td>{row.invoice_count}</td><td className="text-right">{money(row.total_amount)}</td></tr>)}</tbody></table></div></details>
        </section>
        <section className={panel}><h2 className="text-lg font-semibold">Nhà cung cấp theo giá trị hóa đơn</h2><p className="mt-1 text-sm text-[#817B9D]">Sắp xếp từ cao đến thấp. Gộp theo mã số thuế; nếu thiếu thì theo tên đơn vị bán.</p>
          <div className="mt-5 overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-[#F8F6FD]"><tr><th className="p-3">Đơn vị bán</th><th className="p-3">Mã số thuế</th><th className="p-3 text-right">Hóa đơn</th><th className="p-3 text-right">Giá trị</th></tr></thead><tbody>{data.suppliers.map((row, i) => <tr key={`${row.seller_tax_code}-${i}`} className="border-t border-[#EEEAF5]"><td className="min-w-48 p-3 font-medium">{row.seller_name}</td><td className="p-3">{row.seller_tax_code || 'Chưa có'}</td><td className="p-3 text-right">{row.invoice_count}</td><td className="whitespace-nowrap p-3 text-right">{money(row.total_amount)}</td></tr>)}</tbody></table></div>
        </section>
      </>}
      <p className="text-xs leading-5 text-[#817B9D]">Chỉ tính hóa đơn đã ghi nhận. Giá trị hóa đơn chưa được phân loại thành doanh thu hoặc chi phí. Dữ liệu hiển thị theo VND của phiên bản hiện tại.</p>
    </>}
  </div>
}
