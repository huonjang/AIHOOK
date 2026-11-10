import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  ArrowUpRight, BarChart3, CalendarDays, CircleHelp, FileCheck2,
  Layers3, RefreshCw, ScanSearch, Sparkles, UsersRound,
} from 'lucide-react'
import { api, type AnalyticsDashboard } from '../services/api'

const CHART_COLORS = ['#35cde8', '#8485ff', '#4ad7aa', '#4f8fff', '#f7bb70', '#49637e']
const money = (value: number | string) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(Number(value))
const compact = (value: number) => new Intl.NumberFormat('vi-VN', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
const count = (value: number) => new Intl.NumberFormat('vi-VN').format(value)
const formatMonth = (month: string) => { const [year, m] = month.split('-'); return `${m}/${year.slice(-2)}` }

type Filter = { start: string; end: string; revision: number }

export default function DashboardPage() {
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [filter, setFilter] = useState<Filter>({ start: '', end: '', revision: 0 })
  const [data, setData] = useState<AnalyticsDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filterError, setFilterError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    api.getAnalytics(filter.start, filter.end, controller.signal)
      .then(result => { if (!controller.signal.aborted) setData(result) })
      .catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Không thể tải dữ liệu.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [filter])

  const refresh = () => setFilter(current => ({ ...current, revision: current.revision + 1 }))
  function apply() {
    if (Boolean(start) !== Boolean(end) || (start && end && start > end)) {
      setFilterError('Hãy chọn cả hai ngày và bảo đảm ngày bắt đầu không sau ngày kết thúc.')
      return
    }
    setFilterError('')
    setFilter(current => ({ start, end, revision: current.revision + 1 }))
  }
  function reset() {
    setStart(''); setEnd(''); setFilterError('')
    setFilter(current => ({ start: '', end: '', revision: current.revision + 1 }))
  }

  const charts = useMemo(() => {
    if (!data) return { monthly: [], pie: [], top: [], top3: 0, peak: null as AnalyticsDashboard['monthly'][number] | null }
    const monthly = data.monthly.slice(-12).map(item => ({ ...item, amount: Number(item.total_amount), short: formatMonth(item.month) }))
    const total = Number(data.overview.total_amount)
    const top = data.suppliers.slice(0, 6).map(supplier => ({
      name: supplier.seller_name, count: supplier.invoice_count, amount: Number(supplier.total_amount),
    }))
    // Pie charts only represent non-negative parts of a positive whole. Credit notes /
    // negative invoices cannot be meaningfully shown as slices of a pie.
    const canDrawPie = total > 0 && data.suppliers.every(item => Number(item.total_amount) >= 0)
    const five = canDrawPie ? data.suppliers.slice(0, 5) : []
    const fiveTotal = five.reduce((acc, item) => acc + Number(item.total_amount), 0)
    const pie = five.map((item, i) => ({ name: item.seller_name, value: Number(item.total_amount), color: CHART_COLORS[i] }))
    if (canDrawPie && total - fiveTotal > 0.01) pie.push({ name: 'Nhà cung cấp khác', value: Math.max(0, total - fiveTotal), color: CHART_COLORS[5] })
    const top3 = canDrawPie ? data.suppliers.slice(0, 3).reduce((acc, row) => acc + Number(row.total_amount), 0) / total * 100 : 0
    const active = data.monthly.filter(month => month.invoice_count > 0)
    const peak = active.length ? active.reduce((best, month) => Number(month.total_amount) > Number(best.total_amount) ? month : best) : null
    return { monthly, pie, top, top3, peak }
  }, [data])

  const stats = data ? [
    { label: 'Tổng giá trị hóa đơn', value: money(data.overview.total_amount), note: 'Không đồng nghĩa doanh thu hoặc chi phí', icon: Layers3, color: '#35cde8' },
    { label: 'Hóa đơn đã xác nhận', value: count(data.overview.invoice_count), note: 'Đã hoàn thành bước xác nhận', icon: FileCheck2, color: '#4ad7aa' },
    { label: 'Trung bình mỗi hóa đơn', value: money(data.overview.average_amount), note: 'Tính trên hóa đơn đã xác nhận', icon: BarChart3, color: '#928aff' },
    { label: 'Nhà cung cấp', value: count(data.overview.supplier_count), note: 'Gộp theo MST hoặc tên', icon: UsersRound, color: '#f7bb70' },
  ] : []

  return <div className="space-y-6 pb-8">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="space-y-2">
        <p className="app-kicker">Overview / Invoice intelligence</p>
        <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">Trung tâm tổng quan<span className="ml-2 text-[#35cde8]">.</span></h1>
        <p className="app-muted max-w-2xl text-sm leading-6">Một góc nhìn rõ ràng về hóa đơn, đơn vị bán và xu hướng giao dịch đã được ghi nhận.</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Link to="/ai" className="app-button-primary text-sm"><Sparkles size={16}/> Phân tích cùng AI <ArrowUpRight size={15}/></Link>
        <button type="button" className="app-button-secondary" onClick={refresh} disabled={loading} title="Tải lại số liệu"><RefreshCw size={16} className={loading ? 'animate-spin' : ''}/> Làm mới</button>
      </div>
    </header>

    <section className="app-card flex flex-wrap items-end gap-3 p-4 sm:p-5" aria-label="Bộ lọc thời gian">
      <div className="mr-auto flex items-center gap-2 pb-2 text-sm font-semibold text-[#d8e9f9]"><CalendarDays size={18} className="text-[#58dcef]"/> Phạm vi phân tích</div>
      <label className="flex flex-col gap-1.5 text-xs text-[#9cb4d0]">Từ ngày<input className="app-input text-sm" type="date" value={start} onChange={e => setStart(e.target.value)}/></label>
      <label className="flex flex-col gap-1.5 text-xs text-[#9cb4d0]">Đến ngày<input className="app-input text-sm" type="date" value={end} onChange={e => setEnd(e.target.value)}/></label>
      <button type="button" className="app-button-primary text-sm" onClick={apply}>Áp dụng</button>
      <button type="button" className="app-button-secondary" onClick={reset}>Toàn thời gian</button>
      {filterError && <p role="alert" className="w-full text-sm text-[#ffacb9]">{filterError}</p>}
      <p className="w-full text-xs text-[#829bb7]">Đang xem: {filter.start ? `${filter.start} – ${filter.end}` : 'Toàn bộ thời gian'} · Theo ngày lập hóa đơn</p>
    </section>

    {loading && <div role="status" className="app-card p-8 text-[#a8c0db]">Đang đồng bộ dữ liệu phân tích...</div>}
    {error && <div role="alert" className="app-card flex flex-wrap items-center justify-between gap-3 p-5 text-[#ffb4ba]"><span>Không thể tải số liệu: {error}</span><button className="app-button-secondary" onClick={refresh}>Thử lại</button></div>}
    {!loading && data && <>
      <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">
        {stats.map(({ label, value, note, icon: Icon, color }) => <section key={label} className="app-card relative overflow-hidden p-5">
          <div className="absolute -top-8 -right-8 h-28 w-28 rounded-full opacity-10 blur-2xl" style={{ background: color }}/>
          <div className="flex items-center justify-between"><p className="text-sm font-medium text-[#a9bdd3]">{label}</p><span className="flex h-10 w-10 items-center justify-center rounded-xl" style={{background: `${color}18`, color}}><Icon size={19}/></span></div>
          <p className="mt-5 break-words text-2xl font-extrabold tracking-tight text-white xl:text-[1.7rem]">{value}</p>
          <p className="mt-2 text-xs text-[#839db8]">{note}</p>
        </section>)}
      </div>

      <section className="flex flex-col gap-2 rounded-2xl border border-[#365570] bg-[#10253b]/90 p-4 text-sm text-[#accce3] sm:flex-row sm:items-center sm:justify-between">
        <span className="flex items-center gap-2"><CircleHelp size={18} className="shrink-0 text-[#65d8ee]"/><span><strong className="text-[#d7f4ff]">Chưa phân loại thu / chi.</strong> Không thể suy ra doanh thu, chi phí hay lợi nhuận từ hóa đơn hiện có.</span></span>
        <span className="shrink-0 text-xs text-[#8cb7d0]">Định hướng: doanh nghiệp nhỏ · quản lý chứng từ</span>
      </section>
      {data.overview.undated_count > 0 && <p role="note" className="rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">{data.overview.undated_count} hóa đơn thiếu ngày lập vẫn được tính trong tổng toàn thời gian nhưng không nằm trong biểu đồ theo tháng.</p>}

      {data.overview.invoice_count === 0 ? <section className="app-card px-6 py-16 text-center">
        <ScanSearch className="mx-auto text-[#65d9ec]" size={36}/><h2 className="mt-4 text-xl font-bold">Chưa có hóa đơn phù hợp</h2>
        <p className="app-muted mt-2 text-sm">Hãy thay đổi bộ lọc hoặc tải hóa đơn mới lên.</p><Link className="app-button-primary mt-5 text-sm" to="/invoices">Đến trang hóa đơn</Link>
      </section> : <>
        <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.55fr)_minmax(340px,1fr)]">
          <section className="app-card min-w-0 p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="app-kicker">Trend analytics</p><h2 className="mt-2 text-lg font-bold text-white">Giá trị hóa đơn theo tháng</h2><p className="app-muted mt-1 text-xs">{data.monthly.length > 12 ? '12 tháng cuối trong phạm vi đã chọn' : 'Các tháng trong phạm vi đã chọn'} · Đơn vị VND</p></div><span className="app-pill">Xu hướng</span></div>
            <div className="mt-5 h-[280px] min-w-0 sm:h-[310px]" role="img" aria-label="Biểu đồ diện tích giá trị hóa đơn theo tháng">
              <ResponsiveContainer width="100%" height="100%"><AreaChart data={charts.monthly} margin={{left:0,right:8,top:14,bottom:0}}>
                <defs><linearGradient id="dashboardArea" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#35cde8" stopOpacity={0.35}/><stop offset="98%" stopColor="#35cde8" stopOpacity={0}/></linearGradient></defs>
                <CartesianGrid vertical={false} stroke="#27405d" strokeDasharray="3 6"/><XAxis dataKey="short" tick={{fill:'#8ea8c3',fontSize:11}} axisLine={false} tickLine={false}/><YAxis tick={{fill:'#8ea8c3',fontSize:11}} width={65} tickFormatter={v=>compact(Number(v))} axisLine={false} tickLine={false}/>
                <Tooltip contentStyle={{background:'#15263d',border:'1px solid #355477',borderRadius:12,color:'#eaf6ff'}} formatter={v => money(Number(v))} labelFormatter={l=>`Tháng ${l}`}/>
                <Area type="monotone" dataKey="amount" name="Tổng giá trị" stroke="#35cde8" strokeWidth={3} fill="url(#dashboardArea)" activeDot={{r:5,fill:'#35cde8',stroke:'#102034',strokeWidth:3}}/>
              </AreaChart></ResponsiveContainer>
            </div>
          </section>
          <section className="app-card min-w-0 p-5 sm:p-6">
            <p className="app-kicker">Composition</p><h2 className="mt-2 text-lg font-bold text-white">Cơ cấu nhà cung cấp</h2><p className="app-muted mt-1 text-xs">Theo tỷ trọng giá trị hóa đơn, không phải nhóm chi phí</p>
            {charts.pie.length > 0 && charts.pie.some(row=>row.value>0) ? <>
              <div className="relative mt-3 h-[206px] min-w-0" role="img" aria-label="Biểu đồ tròn tỷ trọng giá trị hóa đơn theo nhà cung cấp"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={charts.pie} dataKey="value" nameKey="name" innerRadius={65} outerRadius={91} paddingAngle={2} stroke="#111e32" strokeWidth={2}>{charts.pie.map((entry,i)=><Cell key={entry.name+i} fill={entry.color}/>)}</Pie><Tooltip contentStyle={{background:'#15263d',border:'1px solid #355477',borderRadius:12,color:'#eaf6ff'}} formatter={v=>money(Number(v))}/></PieChart></ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center"><span className="text-2xl font-bold text-white">{charts.top3.toFixed(1)}%</span><span className="text-[10px] text-[#95b1c9]">Top 3 đơn vị bán</span></div></div>
              <div className="grid gap-2 sm:grid-cols-2 2xl:grid-cols-1">{charts.pie.map((entry,i)=><div key={entry.name+i} className="flex min-w-0 items-center gap-2 text-xs text-[#a9bed5]"><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{background:entry.color}}/><span className="min-w-0 flex-1 truncate" title={entry.name}>{entry.name}</span><span className="shrink-0 font-semibold text-[#e5f4ff]">{Number(data.overview.total_amount) > 0 ? (entry.value/Number(data.overview.total_amount)*100).toFixed(1) : '0'}%</span></div>)}</div>
              </> : <p className="app-muted mt-14 text-center text-sm">Không thể vẽ tỷ trọng khi tổng bằng 0 hoặc có giá trị âm cần bù trừ.</p>}
          </section>
        </div>

        <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]">
          <section className="app-card min-w-0 p-5 sm:p-6">
            <p className="app-kicker">Invoice volume</p><h2 className="mt-2 text-lg font-bold text-white">Số lượng hóa đơn theo tháng</h2><p className="app-muted mt-1 text-xs">Số hóa đơn đã được xác nhận · {data.monthly.length > 12 ? '12 tháng cuối' : 'Trong phạm vi lọc'}</p>
            <div className="mt-5 h-[255px] min-w-0" role="img" aria-label="Biểu đồ cột số lượng hóa đơn theo tháng"><ResponsiveContainer width="100%" height="100%"><BarChart data={charts.monthly} margin={{top:10,right:4,left:-12,bottom:0}}><CartesianGrid vertical={false} stroke="#27405d" strokeDasharray="3 6"/><XAxis dataKey="short" tick={{fill:'#8ea8c3',fontSize:11}} axisLine={false} tickLine={false}/><YAxis tick={{fill:'#8ea8c3',fontSize:11}} tickLine={false} axisLine={false} allowDecimals={false}/><Tooltip contentStyle={{background:'#15263d',border:'1px solid #355477',borderRadius:12,color:'#eaf6ff'}}/><Bar dataKey="invoice_count" name="Hóa đơn" fill="#8886ff" radius={[7,7,0,0]} maxBarSize={47}/></BarChart></ResponsiveContainer></div>
          </section>
          <section className="app-card min-w-0 p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-2"><div><p className="app-kicker">Supplier ranking</p><h2 className="mt-2 text-lg font-bold text-white">Nhà cung cấp nổi bật</h2><p className="app-muted mt-1 text-xs">Top 6 theo tổng giá trị · Chỉ hóa đơn đã xác nhận</p></div><span className="app-pill">{data.overview.supplier_count} đơn vị</span></div>
            <div className="mt-5 space-y-3">{charts.top.map((supplier,i)=><div key={supplier.name+i} className="space-y-1.5"><div className="flex items-baseline justify-between gap-3 text-xs"><span className="max-w-[72%] truncate text-[#c5dbeb]" title={supplier.name}>{supplier.name}</span><span className="whitespace-nowrap font-semibold text-[#f0f7ff]">{money(supplier.amount)}</span></div><div className="h-2 overflow-hidden rounded-full bg-[#233953]"><div className="h-full rounded-full" style={{width:`${charts.top[0]?.amount ? Math.max(2, supplier.amount / charts.top[0].amount * 100) : 0}%`,background:CHART_COLORS[i%CHART_COLORS.length]}}/></div></div>)}</div>
          </section>
        </div>

        <section className="app-card overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 p-5 sm:px-6"><div><p className="app-kicker">Data ledger</p><h2 className="mt-2 text-lg font-bold text-white">Bảng đối chiếu theo tháng</h2></div>{charts.peak && <p className="text-xs text-[#9fc0d8]">Cao nhất: <strong className="text-[#65e4f3]">{charts.peak.month} · {money(charts.peak.total_amount)}</strong></p>}</div>
          <div className="overflow-x-auto"><table className="app-table"><thead><tr><th>Tháng</th><th className="text-right!">Hóa đơn</th><th className="text-right!">Giá trị</th></tr></thead><tbody>{data.monthly.map(row=><tr key={row.month}><td>{row.month}</td><td className="text-right!">{count(row.invoice_count)}</td><td className="text-right! font-semibold">{money(row.total_amount)}</td></tr>)}</tbody></table></div>
        </section>
      </>}
      <p className="app-muted text-xs leading-6">Số liệu được tổng hợp từ hóa đơn có trạng thái <strong>confirmed</strong>. Tổng giá trị không phản ánh lợi nhuận, doanh thu hay chi phí khi chưa phân loại chứng từ. Kiểm tra số học nội bộ không thay thế việc kiểm tra hóa đơn gốc.</p>
    </>}
  </div>
}
