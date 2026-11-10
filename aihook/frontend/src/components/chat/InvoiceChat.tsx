import { useEffect, useRef, useState } from 'react'
import {
  ArrowUp, BrainCircuit, CircleCheck, Database, ExternalLink, FileSearch,
  Lightbulb, MessageSquareText, RotateCcw, Send, ShieldCheck, Sparkles,
} from 'lucide-react'
import { api, getInvoiceFileUrl, type ChatReply } from '../../services/api'

const prompts = [
  { title: 'Phân tích tổng quan', question: 'Phân tích tổng quan các hóa đơn đã xác nhận. Nêu xu hướng, điểm đáng chú ý và giới hạn dữ liệu.' },
  { title: 'Nhà cung cấp nổi bật', question: 'Nhà cung cấp nào có tổng giá trị hóa đơn lớn nhất? So sánh nhóm đứng đầu theo tổng giá trị và số lượng.' },
  { title: 'Xu hướng theo tháng', question: 'Tháng nào có tổng giá trị hóa đơn cao nhất? So sánh với các tháng khác đã hoàn tất.' },
  { title: 'Kiểm chứng số liệu', question: 'Kiểm tra tính nhất quán giữa tổng tiền, trung bình, số lượng và thống kê theo tháng.' },
  { title: 'Khuyến nghị quản lý', question: 'Đưa ra 5 khuyến nghị giúp tôi quản lý dữ liệu hóa đơn tốt hơn, dựa trên dữ liệu đã ghi nhận.' },
]

type ChatMessage = { question: string; reply: ChatReply }

function AnswerText({ value }: { value: string }) {
  const normalized = value.replace(/\s*•\s+/g, '\n• ').trim()
  const lines = normalized.split(/\n+/).map(line => line.trim()).filter(Boolean)
  return <div className="space-y-2.5 text-sm leading-7 text-[#d8e8f8]">
    {lines.map((line, index) => line.startsWith('• ') ? <div key={index} className="flex gap-2.5 pl-1"><span className="mt-[11px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#56d9ea]"/><p className="min-w-0">{line.slice(2)}</p></div>
      : /^(Nhận xét|Khuyến nghị|Gợi ý bổ sung|Kết luận|Lưu ý)[^\n]{0,90}:$/.test(line)
        ? <h3 key={index} className="pt-2 text-sm font-bold text-[#8cecf8]">{line}</h3>
        : <p key={index} className="whitespace-pre-wrap break-words">{line}</p>)}
  </div>
}

export default function InvoiceChat({start, end}: {start: string; end: string}) {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<ChatMessage[]>([])
  const [configured, setConfigured] = useState(false)
  const [checking, setChecking] = useState(true)
  const [useAI, setUseAI] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const active = useRef(true)
  const feed = useRef<HTMLDivElement>(null)

  useEffect(() => {
    active.current = true
    api.getChatStatus().then(status => {
      if (active.current) { setConfigured(status.ai_configured); setUseAI(status.ai_configured) }
    }).catch(() => { if (active.current) setError('Không kiểm tra được cấu hình AI. Bạn vẫn có thể thử chế độ dữ liệu nội bộ.') })
      .finally(() => { if (active.current) setChecking(false) })
    return () => { active.current = false }
  }, [])
  useEffect(() => { feed.current?.scrollTo({ top: feed.current.scrollHeight, behavior: 'smooth' }) }, [history.length, busy])

  async function ask(message = question) {
    const cleaned = message.trim()
    if (!cleaned || busy) return
    setBusy(true); setError('')
    try {
      const reply = await api.askQuestion(cleaned, start, end, useAI)
      if (active.current) { setHistory(items => [...items, { question: cleaned, reply }]); setQuestion('') }
    } catch (cause) { if (active.current) setError(cause instanceof Error ? cause.message : 'Không thể nhận phản hồi.') }
    finally { if (active.current) setBusy(false) }
  }

  return <section className="grid min-h-[650px] gap-5 xl:grid-cols-[250px_minmax(0,1fr)]">
    <aside className="app-card self-start p-5 xl:sticky xl:top-6">
      <div className="flex items-center gap-2"><Lightbulb size={17} className="text-[#73dfed]"/><h2 className="text-sm font-bold text-white">Gợi ý khám phá</h2></div>
      <p className="app-muted mt-2 text-xs leading-5">Bắt đầu với một câu hỏi mẫu hoặc tự đặt câu hỏi về dữ liệu của bạn.</p>
      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
        {prompts.map(prompt => <button key={prompt.title} type="button" disabled={busy} onClick={()=>void ask(prompt.question)} className="group flex items-center justify-between gap-2 rounded-xl border border-[#2c435e] bg-[#14243a] px-3 py-3 text-left text-xs font-semibold text-[#ccdeef] transition-colors hover:border-[#4986a5] hover:bg-[#1a3550] disabled:opacity-50"><span>{prompt.title}</span><ArrowUp size={13} className="shrink-0 rotate-45 text-[#66dce9]"/></button>)}
      </div>
      <div className="mt-6 border-t border-[#30425d] pt-5">
        <p className="text-xs font-bold text-[#a5c1d9]">Chế độ phản hồi</p>
        <label className="mt-3 flex cursor-pointer items-center justify-between gap-3 text-xs text-[#cadff0]"><span className="flex items-center gap-2"><Sparkles size={15} className="text-[#69dded]"/> AI phân tích tự do</span><input type="checkbox" className="h-4 w-4 accent-[#37d1e8]" checked={useAI} disabled={!configured || busy || checking} onChange={e=>setUseAI(e.target.checked)}/></label>
        <p className="app-muted mt-2 text-xs leading-5">{checking ? 'Đang kiểm tra Ollama / AI...' : configured ? useAI ? 'Backend truy vấn và kiểm chứng số liệu; AI diễn giải. Không gửi PDF hay raw OCR cho model.' : 'Chế độ nội bộ không gọi LLM, chỉ dựa trên dữ liệu trong hệ thống.' : 'Chưa cấu hình AI trên backend. Có thể hỏi đáp dữ liệu nội bộ.'}</p>
        <div className="mt-4 flex items-center gap-2 rounded-xl border border-[#30425d] bg-[#102138] p-3 text-xs text-[#9bb8d1]"><ShieldCheck className="shrink-0 text-[#47deb0]" size={17}/><span>Truy vấn chỉ đọc · Kiểm chứng số học</span></div>
      </div>
    </aside>

    <div className="app-card flex min-w-0 flex-col overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#2a3b55] px-5 py-4 sm:px-7">
        <div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#34cbeb]/15 text-[#6ee7f6]"><BrainCircuit size={21}/></div><div><h2 className="font-bold text-white">AIHOOK Intelligence</h2><p className="text-xs text-[#88a7c2]">{start ? `Dữ liệu ${start} → ${end}` : 'Toàn bộ thời gian'} · Câu hỏi độc lập</p></div></div>
        <div className="flex items-center gap-2"><span className="app-pill">{useAI && configured ? 'AI enabled' : 'Local data'}</span><button className="app-button-secondary px-3! py-2! text-xs" onClick={()=>setHistory([])} disabled={busy || history.length===0} title="Xóa lịch sử hiển thị (không xóa dữ liệu hóa đơn)"><RotateCcw size={14}/> Xóa hội thoại</button></div>
      </header>
      <div ref={feed} className="min-h-[360px] max-h-[70vh] flex-1 space-y-6 overflow-y-auto px-4 py-6 sm:px-7" aria-live="polite" aria-busy={busy}>
        {history.length===0 && <div className="mx-auto flex max-w-xl flex-col items-center justify-center py-20 text-center"><div className="flex h-16 w-16 items-center justify-center rounded-[23px] border border-[#3b657e] bg-[#21516b]/30 text-[#7fe6f7] shadow-[0_0_45px_#35cde811]"><MessageSquareText size={29}/></div><h3 className="mt-5 text-2xl font-extrabold text-white">Bạn muốn khám phá điều gì?</h3><p className="app-muted mt-3 text-sm leading-7">Hỏi về tổng giá trị, hóa đơn cụ thể, nhà cung cấp hoặc xu hướng theo thời gian. AI sẽ sử dụng các công cụ truy vấn an toàn để trả lời trên dữ liệu đã lưu.</p><div className="mt-4 flex items-center gap-2 text-xs text-[#70cddf]"><CircleCheck size={15}/> Không tự suy diễn doanh thu hoặc chi phí</div></div>}
        {history.map((item,index)=><article key={index} className="space-y-4">
          <div className="ml-auto max-w-[85%] rounded-2xl rounded-tr-sm border border-[#305c78] bg-[#1a3d59] px-4 py-3 text-sm leading-6 text-[#e7f9ff]">{item.question}</div>
          <div className="rounded-2xl border border-[#2a405d] bg-[#12233a] p-4 sm:p-5">
            <div className="mb-4 flex flex-wrap items-center gap-2"><span className="flex items-center gap-1.5 text-xs font-bold text-[#78e3f0]"><Sparkles size={15}/> {item.reply.mode === 'ai' ? 'AIHOOK Assistant' : 'Dữ liệu nội bộ'}</span><span className="text-xs text-[#809ab7]">· {item.reply.scope}</span></div>
            <AnswerText value={item.reply.answer}/>
            {item.reply.validation && item.reply.validation.status !== 'not_applicable' && <div className={`mt-5 rounded-xl border px-3 py-3 text-xs ${item.reply.validation.status === 'passed' ? 'border-emerald-400/30 bg-emerald-500/10 text-[#8ce4be]' : 'border-amber-400/30 bg-amber-500/10 text-[#ffd48b]'}`}><div className="flex items-center gap-2 font-semibold"><ShieldCheck size={15}/>{item.reply.validation.status === 'passed' ? 'Đối chiếu số học nội bộ đã đạt' : 'Cần kiểm tra số liệu'} · {item.reply.validation.passed_checks}/{item.reply.validation.total_checks}</div><p className="mt-1.5 opacity-80">Không thay thế kiểm tra OCR hoặc xác minh tính hợp pháp của hóa đơn.</p>{item.reply.validation.status==='warning' && <ul className="mt-2 list-disc pl-4">{item.reply.validation.checks.filter(check=>!check.passed).map(check=><li key={check.code}>{check.label}: dự kiến {check.expected}, thực tế {check.actual}</li>)}</ul>}</div>}
            {item.reply.evidence && item.reply.evidence.length>0 && <details className="mt-4 rounded-xl border border-[#344b67] bg-[#101d30] p-3.5 text-sm"><summary className="flex cursor-pointer items-center gap-2 font-semibold text-[#89e3f1]"><Database size={16}/> Số liệu backend đã kiểm chứng</summary><div className="mt-4 space-y-4">{item.reply.evidence.map((ev,i)=><div key={`${ev.title}-${i}`}><h4 className="mb-2 text-sm font-semibold text-white">{ev.title}</h4><div className="overflow-x-auto"><table className="app-table text-xs"><thead><tr>{ev.columns.map((col,j)=><th key={j}>{col}</th>)}</tr></thead><tbody>{ev.rows.map((row,j)=><tr key={j}>{row.map((cell,k)=><td key={k}>{cell ?? '—'}</td>)}</tr>)}</tbody></table></div></div>)}</div></details>}
            {item.reply.sources.length>0 && <details className="mt-3 rounded-xl border border-[#344b67] bg-[#101d30] p-3.5 text-sm"><summary className="flex cursor-pointer items-center gap-2 font-semibold text-[#89e3f1]"><FileSearch size={16}/> Hóa đơn đối chiếu ({item.reply.sources.length})</summary><p className="app-muted mt-2 text-xs">{item.reply.source_note}</p><ul className="mt-3 space-y-2">{item.reply.sources.map(source=><li key={source.invoice_id}><a className="flex items-start gap-2 text-sm text-[#70def5] hover:underline" href={getInvoiceFileUrl(source.invoice_id)} target="_blank" rel="noreferrer"><ExternalLink size={15} className="mt-1 shrink-0"/><span>{source.invoice_number || `Hóa đơn #${source.invoice_id}`}{source.seller_name ? ` · ${source.seller_name}` : ''}{source.invoice_date ? ` · ${source.invoice_date}` : ''}{source.source_page ? ` · Trang ${source.source_page}` : ''}</span></a></li>)}</ul></details>}
            {item.reply.tools_used && item.reply.tools_used.length>0 && <p className="mt-4 break-words text-[11px] text-[#769ab6]">Function Calling · {item.reply.tools_used.join(' · ')}</p>}
          </div>
        </article>)}
        {busy && <div role="status" className="flex items-center gap-3 rounded-xl border border-[#35526b] bg-[#15273e] px-4 py-4 text-sm text-[#b6d5e8]"><span className="h-2.5 w-2.5 animate-pulse rounded-full bg-[#35cde8]"/> Đang truy vấn và phân tích dữ liệu. Với model local, quá trình này có thể mất một lúc...</div>}
      </div>
      <div className="border-t border-[#2a3b55] bg-[#0e1c30]/85 p-4 sm:p-5">
        {error && <p role="alert" className="mb-3 rounded-xl border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-sm text-[#ffadbb]">{error}</p>}
        <form className="flex items-end gap-3" onSubmit={event=>{event.preventDefault();void ask()}}><label className="min-w-0 flex-1"><span className="sr-only">Câu hỏi về hóa đơn</span><textarea className="app-input min-h-[62px] w-full resize-y text-sm leading-6" rows={2} value={question} onChange={e=>setQuestion(e.target.value)} maxLength={2000} placeholder="Hỏi bất kỳ điều gì về hóa đơn đã import..." onKeyDown={e=>{if(e.key==='Enter' && !e.shiftKey && !e.nativeEvent.isComposing){e.preventDefault();void ask()}}}/></label><button type="submit" className="app-button-primary mb-1 h-12 px-4!" disabled={busy || !question.trim()} aria-label="Gửi câu hỏi"><Send size={18}/><span className="hidden sm:inline">Gửi</span></button></form>
        <p className="mt-2 text-center text-[11px] text-[#7692ac]">Enter để gửi · Shift+Enter xuống dòng · AI có thể đưa ra nhận định chưa đầy đủ; kiểm tra bảng số liệu và hóa đơn nguồn.</p>
      </div>
    </div>
  </section>
}
