import { useState } from 'react'
import { BrainCircuit, CalendarDays, DatabaseZap, ShieldCheck, Sparkles } from 'lucide-react'
import InvoiceChat from '../components/chat/InvoiceChat'

type Scope = { start: string; end: string }

export default function AIAssistantPage() {
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [scope, setScope] = useState<Scope>({ start: '', end: '' })
  const [error, setError] = useState('')
  function applyScope() {
    if (Boolean(start) !== Boolean(end) || (start && end && start > end)) {
      setError('Hãy chọn đủ hai ngày và kiểm tra thứ tự ngày.'); return
    }
    setError(''); setScope({ start, end })
  }
  function clearScope() {
    setStart(''); setEnd(''); setError(''); setScope({ start:'', end:'' })
  }
  return <div className="space-y-6 pb-4">
    <header className="relative overflow-hidden rounded-[26px] border border-[#315372] bg-[linear-gradient(120deg,#142b49,#102139_55%,#13284a)] p-6 sm:p-8">
      <div className="pointer-events-none absolute -top-24 right-0 h-72 w-72 rounded-full bg-[#4ddff3]/10 blur-3xl"/>
      <div className="pointer-events-none absolute right-1/4 -bottom-28 h-60 w-60 rounded-full bg-[#8584ff]/10 blur-3xl"/>
      <div className="relative flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-[740px]">
          <div className="flex items-center gap-2"><span className="app-pill inline-flex items-center gap-1.5"><Sparkles size={13}/> AI-powered workspace</span><span className="text-[10px] font-bold tracking-[.2em] text-[#8aa5c4]">FEATURED</span></div>
          <h1 className="mt-4 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">AI Assistant<span className="text-[#4bd9f0]">.</span></h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-[#b6cee3]">Hỏi tự nhiên, truy vấn đúng hóa đơn và khám phá những điều đáng chú ý. Số liệu được tính ở backend; AI diễn giải để bạn dễ hiểu và ra quyết định có cơ sở.</p>
        </div>
        <div className="flex items-center gap-2 self-start rounded-2xl border border-[#47657e] bg-[#10243e]/70 px-4 py-3 text-xs text-[#b9dcf2]"><ShieldCheck size={18} className="text-[#48e5b1]"/><span>Chỉ đọc dữ liệu<br/><span className="text-[#83a6c1]">Numerical Validation</span></span></div>
      </div>
      <div className="relative mt-6 flex flex-wrap gap-2 text-xs text-[#aad0e5]">
        <span className="inline-flex items-center gap-2 rounded-full border border-[#35536e] bg-[#183653] px-3 py-1.5"><DatabaseZap size={14} className="text-[#55dff0]"/> SQL-backed insights</span>
        <span className="inline-flex items-center gap-2 rounded-full border border-[#35536e] bg-[#183653] px-3 py-1.5"><BrainCircuit size={14} className="text-[#a6a0ff]"/> Ollama / OpenAI compatible</span>
      </div>
    </header>

    <section className="app-card flex flex-wrap items-end gap-3 p-4 sm:p-5" aria-label="Phạm vi dữ liệu AI">
      <div className="mr-auto flex items-center gap-2 pb-2 text-sm font-semibold text-[#d7e7fa]"><CalendarDays size={18} className="text-[#5ddaf3]"/> Phạm vi dữ liệu AI</div>
      <label className="flex flex-col gap-1.5 text-xs text-[#9fb6cc]">Từ ngày<input className="app-input text-sm" type="date" value={start} onChange={e=>setStart(e.target.value)}/></label>
      <label className="flex flex-col gap-1.5 text-xs text-[#9fb6cc]">Đến ngày<input className="app-input text-sm" type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label>
      <button className="app-button-primary text-sm" type="button" onClick={applyScope}>Áp dụng</button><button className="app-button-secondary" type="button" onClick={clearScope}>Toàn thời gian</button>
      {error && <p role="alert" className="w-full text-sm text-[#ffb2bb]">{error}</p>}
      <p className="w-full text-xs text-[#829eb8]">Áp dụng bộ lọc sẽ bắt đầu một phiên hiển thị mới; các câu hỏi vẫn được backend xử lý độc lập, chưa có ghi nhớ hội thoại.</p>
    </section>

    <InvoiceChat key={`${scope.start}:${scope.end}`} start={scope.start} end={scope.end}/>
  </div>
}
