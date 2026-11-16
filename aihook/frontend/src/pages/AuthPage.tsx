import { useState, type FormEvent } from 'react'
import { Building2, LockKeyhole, Mail, ScanLine, ShieldCheck, UserRound, ArrowRight, Phone } from 'lucide-react'
import { accountApi, type AccountProfile } from '../services/api'

export default function AuthPage({ onAuthenticated }: { onAuthenticated: (profile: AccountProfile) => void }) {
  const [signup, setSignup] = useState(false)
  const [form, setForm] = useState({ email: '', password: '', business_name: '', owner_name: '', tax_code: '', phone: '' })
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)
  const update = (name: keyof typeof form, value: string) => setForm(current => ({ ...current, [name]: value }))
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (working) return
    setError('')
    setWorking(true)
    try {
      if (signup && form.password.length < 10) throw new Error('Mật khẩu cần ít nhất 10 ký tự.')
      const account = signup
        ? await accountApi.register({ ...form, tax_code: form.tax_code.trim() || undefined, phone: form.phone.trim() || undefined })
        : await accountApi.login({ email: form.email, password: form.password })
      onAuthenticated(account)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể kết nối dịch vụ tài khoản.')
    } finally { setWorking(false) }
  }
  return <main className="app-shell grid min-h-screen place-items-center px-4 py-10">
    <div className="grid w-full max-w-5xl overflow-hidden rounded-[28px] border border-[#2d4b67] bg-[#0d1a2d] shadow-[0_28px_80px_rgba(0,0,0,.4)] lg:grid-cols-[1fr_1.12fr]">
      <aside className="relative overflow-hidden border-b border-[#294360] bg-[linear-gradient(145deg,#0d3150,#102139_65%,#0b172b)] p-7 lg:border-r lg:border-b-0 lg:p-10">
        <div className="pointer-events-none absolute -top-20 -right-32 h-96 w-96 rounded-full bg-[#2ed3e7]/15 blur-3xl" />
        <div className="relative inline-flex items-center gap-3"><span className="grid size-12 place-items-center rounded-2xl border border-[#66e5f4]/25 bg-[#35cde8]/15 text-[#7ceaff]"><ScanLine size={27}/></span><span className="text-2xl font-black tracking-wider text-white">AIHOOK</span></div>
        <p className="app-kicker relative mt-14">Invoice intelligence</p>
        <h1 className="relative mt-4 text-3xl font-extrabold leading-tight text-white sm:text-4xl">Hiểu dữ liệu hóa đơn.<br/><span className="text-[#64dff2]">Quyết định có cơ sở.</span></h1>
        <p className="relative mt-6 max-w-sm text-sm leading-7 text-[#abc6db]">Một không gian riêng cho từng doanh nghiệp để quản lý hóa đơn mua vào, bán ra và đặt câu hỏi với trợ lý AI.</p>
        <div className="relative mt-9 space-y-4 text-sm text-[#bfd9e9]">
          <p className="flex items-center gap-3"><ShieldCheck size={19} className="text-[#4de5b8]"/>Dữ liệu được tách theo tài khoản doanh nghiệp</p>
          <p className="flex items-center gap-3"><Building2 size={19} className="text-[#75dcf2]"/>Mã số thuế không bắt buộc</p>
          <p className="flex items-center gap-3"><LockKeyhole size={19} className="text-[#afacff]"/>Đăng nhập để truy cập hóa đơn và AI</p>
        </div>
      </aside>
      <section className="p-6 sm:p-9 lg:p-10">
        <div className="flex items-center justify-between gap-3"><div><p className="app-kicker">Business account</p><h2 className="mt-2 text-2xl font-extrabold text-white">{signup ? 'Tạo tài khoản doanh nghiệp' : 'Chào mừng quay lại'}</h2></div><span className="app-pill">MVP</span></div>
        <p className="app-muted mt-3 text-sm">{signup ? 'Mỗi tài khoản hiện quản lý một doanh nghiệp.' : 'Đăng nhập để tiếp tục với dữ liệu riêng của bạn.'}</p>
        <form onSubmit={event => void submit(event)} className="mt-7 space-y-4">
          {signup && <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm text-[#c7ddf0]"><span className="flex items-center gap-2"><Building2 size={15}/>Tên doanh nghiệp *</span><input className="app-input w-full" required maxLength={255} minLength={2} value={form.business_name} onChange={e => update('business_name', e.target.value)} placeholder="Cửa hàng / Công ty ABC"/></label>
            <label className="flex flex-col gap-2 text-sm text-[#c7ddf0]"><span className="flex items-center gap-2"><UserRound size={15}/>Tên chủ doanh nghiệp *</span><input className="app-input w-full" required maxLength={150} minLength={2} value={form.owner_name} onChange={e => update('owner_name', e.target.value)} placeholder="Nguyễn Văn A"/></label>
            <label className="flex flex-col gap-2 text-sm text-[#c7ddf0]"><span>Mã số thuế (không bắt buộc)</span><input className="app-input w-full" maxLength={30} value={form.tax_code} onChange={e => update('tax_code', e.target.value)} placeholder="Có thể bổ sung sau"/></label>
            <label className="flex flex-col gap-2 text-sm text-[#c7ddf0]"><span className="flex items-center gap-2"><Phone size={15}/>Số điện thoại (tùy chọn)</span><input className="app-input w-full" maxLength={30} type="tel" value={form.phone} onChange={e => update('phone', e.target.value)} placeholder="Số liên lạc"/></label>
          </div>}
          <label className="flex flex-col gap-2 text-sm text-[#c7ddf0]"><span className="flex items-center gap-2"><Mail size={15}/>Email *</span><input className="app-input w-full" required type="email" autoComplete="email" maxLength={254} value={form.email} onChange={e => update('email', e.target.value)} placeholder="you@business.com"/></label>
          <label className="flex flex-col gap-2 text-sm text-[#c7ddf0]"><span className="flex items-center gap-2"><LockKeyhole size={15}/>Mật khẩu *</span><input className="app-input w-full" required type="password" autoComplete={signup ? 'new-password' : 'current-password'} minLength={signup ? 10 : undefined} maxLength={128} value={form.password} onChange={e => update('password', e.target.value)} placeholder={signup ? 'Ít nhất 10 ký tự' : 'Nhập mật khẩu'} /></label>
          {signup && <p className="text-xs leading-5 text-[#94b2ca]">Mã số thuế chỉ dùng hỗ trợ đối chiếu vai trò bên mua/bán. AIHOOK không thay thế xác minh pháp lý hoặc kế toán. Hóa đơn mới mặc định chưa phân loại.</p>}
          {error && <p className="rounded-xl border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-200" role="alert">{error}</p>}
          <button className="app-button-primary w-full text-sm" disabled={working} type="submit">{working ? 'Đang xử lý...' : signup ? 'Tạo tài khoản' : 'Đăng nhập'}<ArrowRight size={17}/></button>
        </form>
        <p className="mt-6 text-center text-sm text-[#9eb7ce]">{signup ? 'Đã có tài khoản?' : 'Chưa có tài khoản?'} <button className="font-semibold text-[#68e5f4] hover:underline" onClick={() => { setSignup(!signup); setError('') }}>{signup ? 'Đăng nhập' : 'Đăng ký doanh nghiệp'}</button></p>
      </section>
    </div>
  </main>
}
