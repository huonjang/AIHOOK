import { NavLink, Outlet } from 'react-router-dom'
import { LayoutDashboard, FileText, Sparkles, ScanLine, ShieldCheck, UserRound } from 'lucide-react'

const navigation = [
  { to: '/', label: 'Tổng quan', icon: LayoutDashboard, end: true },
  { to: '/invoices', label: 'Hóa đơn', icon: FileText, end: false },
  { to: '/ai', label: 'AI Assistant', icon: Sparkles, end: false },
]

export default function MainLayout() {
  return <div className="app-shell md:flex">
    <aside className="relative z-10 w-full shrink-0 border-b border-[#273955] bg-[#0b1527]/95 md:fixed md:inset-y-0 md:w-[246px] md:border-b-0 md:border-r md:overflow-y-auto">
      <div className="flex items-center gap-3 px-5 pt-6 pb-5 md:pb-9">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] border border-cyan-300/25 bg-gradient-to-br from-cyan-300/25 to-blue-600/20 text-[#68e6f5] shadow-[0_0_26px_rgba(45,201,239,.12)]">
          <ScanLine size={23} strokeWidth={2.3} aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5"><span className="text-xl font-black tracking-[.07em] text-white">AIHOOK</span><span className="h-1.5 w-1.5 rounded-full bg-[#41d7f2]" /></div>
          <p className="text-[10px] font-semibold tracking-[.17em] text-[#7795b5]">INVOICE INTELLIGENCE</p>
        </div>
      </div>
      <p className="hidden px-7 pb-3 text-[10px] font-bold tracking-[.18em] text-[#6884a6] uppercase md:block">Workspace</p>
      <nav className="flex gap-2 px-4 pb-4 md:flex-col md:gap-1.5" aria-label="Điều hướng chính">
        {navigation.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({isActive}) =>
          `group flex min-w-0 flex-1 items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold transition-all md:flex-none ${isActive ? 'border border-cyan-300/15 bg-[#213c55] text-[#84ecfa] shadow-[inset_3px_0_0_#35cde8]' : 'border border-transparent text-[#9bb2ce] hover:bg-[#1b2c43] hover:text-white'}`
        }><Icon size={19} strokeWidth={1.9} aria-hidden="true"/><span className="truncate">{label}</span>{to === '/ai' && <span className="ml-auto hidden rounded-md bg-[#35cde8]/15 px-1.5 py-0.5 text-[9px] tracking-wider text-[#79e6f5] md:inline">NEW</span>}</NavLink>)}
      </nav>
      <div className="mt-auto hidden px-5 pt-8 pb-6 md:block md:absolute md:right-0 md:bottom-0 md:left-0">
        <div className="border-t border-[#263953] pt-5">
          <div className="flex items-center gap-2.5 text-xs text-[#91a8c3]"><ShieldCheck size={16} className="text-[#4ee0ae]"/><span>Số liệu được đối chiếu nội bộ</span></div>
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-[#263953] bg-[#111e32] px-3 py-3 text-xs text-[#7391ae]" title="Quản lý tài khoản sẽ được bổ sung sau">
            <UserRound size={16}/> Tài khoản <span className="ml-auto text-[10px]">Sắp có</span>
          </div>
        </div>
      </div>
    </aside>
    <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 md:ml-[246px] md:px-7 md:py-8 xl:px-10">
      <div className="mx-auto w-full max-w-[1700px]"><Outlet /></div>
    </main>
  </div>
}
