import { useEffect, useState, type FormEvent } from 'react'
import { Building2, Mail, Save, ShieldCheck, UserRound } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { accountApi } from '../services/api'

export default function AccountPage() {
  const { profile, onAuthenticated } = useAuth()
  const [form, setForm] = useState({ business_name: profile?.business.name || '', owner_name: profile?.owner_name || '', tax_code: profile?.business.tax_code || '', phone: profile?.phone || '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  useEffect(() => { if (profile) setForm({ business_name: profile.business.name, owner_name: profile.owner_name, tax_code: profile.business.tax_code || '', phone: profile.phone || '' }) }, [profile])
  if (!profile) return null
  const update = (key: keyof typeof form, value: string) => { setForm(old => ({ ...old, [key]: value })); setSaved(false) }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setSaving(true); setSaved(false)
    try {
      const next = await accountApi.updateProfile({ business_name: form.business_name, owner_name: form.owner_name, tax_code: form.tax_code || null, phone: form.phone || null })
      onAuthenticated(next); setSaved(true)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Không thể lưu hồ sơ.') }
    finally { setSaving(false) }
  }
  return <div className="space-y-6 pb-8">
    <header><p className="app-kicker">Account / Workspace</p><h1 className="mt-2 text-3xl font-extrabold text-white">Tài khoản doanh nghiệp</h1><p className="app-muted mt-2 text-sm">Chỉnh sửa hồ sơ; dữ liệu hóa đơn vẫn thuộc tài khoản này.</p></header>
    <form onSubmit={event => void submit(event)} className="app-card max-w-3xl space-y-6 p-6 sm:p-8">
      <div className="grid gap-5 sm:grid-cols-2">
        <label className="flex flex-col gap-2 text-sm text-[#b4d4e8]"><span className="flex items-center gap-2"><Building2 size={16}/>Tên doanh nghiệp *</span><input className="app-input" minLength={2} maxLength={255} required value={form.business_name} onChange={e => update('business_name', e.target.value)}/></label>
        <label className="flex flex-col gap-2 text-sm text-[#b4d4e8]"><span className="flex items-center gap-2"><UserRound size={16}/>Chủ doanh nghiệp *</span><input className="app-input" minLength={2} maxLength={150} required value={form.owner_name} onChange={e => update('owner_name', e.target.value)}/></label>
        <label className="flex flex-col gap-2 text-sm text-[#b4d4e8]"><span>Mã số thuế (tùy chọn)</span><input className="app-input" maxLength={30} value={form.tax_code} onChange={e => update('tax_code', e.target.value)} placeholder="Có thể để trống"/></label>
        <label className="flex flex-col gap-2 text-sm text-[#b4d4e8]"><span>Số điện thoại (tùy chọn)</span><input type="tel" className="app-input" maxLength={30} value={form.phone} onChange={e => update('phone', e.target.value)}/></label>
      </div>
      <div className="rounded-xl border border-[#2b506b] bg-[#10243b] p-4 text-sm text-[#b9d5ea]"><p className="flex items-center gap-2"><Mail size={16} className="text-[#74def4]"/>Email đăng nhập: <strong className="break-all text-[#e8f6ff]">{profile.email}</strong></p><p className="mt-2 text-xs text-[#93b1ca]">Việc đổi email và khôi phục mật khẩu sẽ được bổ sung khi triển khai xác minh email.</p></div>
      <p className="flex items-start gap-2 rounded-xl border border-[#31516b] bg-[#102640] p-4 text-sm leading-6 text-[#bad3e6]"><ShieldCheck className="mt-0.5 shrink-0 text-[#4de0b5]" size={19}/>Mã số thuế chỉ là dữ liệu đối chiếu nhận dạng và gợi ý hướng hóa đơn, không tự thay đổi loại hóa đơn đã được bạn phân loại.</p>
      {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}{saved && <p role="status" className="text-sm text-emerald-300">Đã lưu hồ sơ doanh nghiệp.</p>}
      <div className="flex justify-end"><button type="submit" className="app-button-primary text-sm" disabled={saving}><Save size={16}/>{saving ? 'Đang lưu...' : 'Lưu thay đổi'}</button></div>
    </form>
  </div>
}
