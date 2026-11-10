import { useEffect, useRef, useState } from 'react'
import { api, getInvoiceFileUrl, type ChatReply } from '../../services/api'

const prompts = ['Tóm tắt dữ liệu', 'Nhà cung cấp nào có giá trị lớn nhất?', 'Tháng nào có giá trị lớn nhất?', 'Hóa đơn nào có giá trị lớn nhất?']
export default function InvoiceChat({ start, end }: { start: string; end: string }) {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<{ question: string; reply: ChatReply }[]>([])
  const [configured, setConfigured] = useState(false)
  const [useAI, setUseAI] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const active = useRef(true)
  useEffect(() => { active.current = true; api.getChatStatus().then(s => { if (active.current) setConfigured(s.ai_configured) }).catch(() => {}); return () => { active.current = false } }, [])
  async function ask(message = question) {
    if (!message.trim() || busy) return
    setBusy(true); setError('')
    try {
      const reply = await api.askQuestion(message, start, end, useAI)
      if (active.current) { setHistory(items => [...items, { question: message, reply }]); setQuestion('') }
    } catch (reason) { if (active.current) setError(reason instanceof Error ? reason.message : 'Không thể trả lời.') }
    finally { if (active.current) setBusy(false) }
  }
  return <section className="rounded-2xl border border-[#E7E1F3] bg-white p-5 shadow-sm">
    <h2 className="text-xl font-semibold">Hỏi đáp về hóa đơn</h2>
    <p className="mt-2 text-sm text-[#817B9D]">Phạm vi: {start ? `${start} đến ${end}` : 'Toàn bộ thời gian'}. Mỗi câu hỏi được xử lý độc lập, chỉ đọc dữ liệu đã ghi nhận.</p>
    <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={useAI} disabled={!configured || busy} onChange={e => setUseAI(e.target.checked)} />Dùng AI để hỏi tự do {configured ? '' : '(chưa cấu hình trên backend)'}</label>
    <p className="mt-2 text-xs text-[#817B9D]">{useAI ? 'Câu hỏi, thống kê và một số trường hóa đơn sẽ được gửi đến dịch vụ AI đã cấu hình. PDF và văn bản OCR gốc không được gửi.' : 'Chế độ nội bộ: trả lời trực tiếp từ số liệu bằng các câu gợi ý, không dùng mô hình AI và không gửi dữ liệu ra ngoài.'}</p>
    <div className="mt-4 flex flex-wrap gap-2">{prompts.map(prompt => <button key={prompt} disabled={busy} onClick={() => ask(prompt)} className="rounded-full border border-[#E7E1F3] px-3 py-2 text-sm text-[#7567BC] disabled:opacity-50">{prompt}</button>)}</div>
    <div className="mt-4 max-h-[480px] space-y-4 overflow-y-auto" aria-live="polite">{history.map((item, index) => <article key={index} className="rounded-xl bg-[#F8F6FD] p-4">
      <p className="font-semibold">{item.question}</p><p className="mt-1 text-xs text-[#817B9D]">{item.reply.mode === 'ai' ? 'AI' : 'Dữ liệu nội bộ'} · {item.reply.scope}</p><p className="mt-3 whitespace-pre-wrap text-sm leading-6">{item.reply.answer}</p>
      {item.reply.sources.length > 0 && <details className="mt-3 text-sm"><summary className="cursor-pointer text-[#7567BC]">Hóa đơn để đối chiếu</summary><p className="mt-2 text-xs text-[#817B9D]">{item.reply.source_note}</p><ul className="mt-2 space-y-1">{item.reply.sources.map(source => <li key={source.invoice_id}><a href={getInvoiceFileUrl(source.invoice_id)} target="_blank" rel="noreferrer" className="underline">{source.invoice_number || `Hóa đơn #${source.invoice_id}`}{source.source_page ? ` · Trang ${source.source_page}` : ''}</a></li>)}</ul></details>}
    </article>)}</div>
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    <form className="mt-4 flex flex-col gap-3 sm:flex-row" onSubmit={event => { event.preventDefault(); void ask() }}><label className="flex-1"><span className="sr-only">Câu hỏi</span><textarea value={question} maxLength={2000} onChange={e => setQuestion(e.target.value)} placeholder="Nhập câu hỏi về hóa đơn..." rows={2} className="w-full rounded-xl border border-[#E7E1F3] p-3 text-sm" /></label><button disabled={busy || !question.trim()} className="rounded-xl bg-[#8C7BEF] px-5 py-3 text-sm font-medium text-white disabled:opacity-50">{busy ? 'Đang trả lời...' : 'Gửi câu hỏi'}</button></form>
  </section>
}
