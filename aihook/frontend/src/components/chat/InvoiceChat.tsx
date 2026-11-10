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
    <p className="mt-2 text-xs text-[#817B9D]">{useAI ? 'AI tự chọn công cụ truy vấn chỉ đọc. Backend tính và kiểm tra số liệu; chỉ kết quả cần thiết được gửi cho model. PDF và văn bản OCR gốc không được gửi.' : 'Chế độ nội bộ: trả lời trực tiếp từ số liệu bằng các câu gợi ý, không dùng mô hình AI và không gửi dữ liệu ra ngoài.'}</p>
    <div className="mt-4 flex flex-wrap gap-2">{prompts.map(prompt => <button key={prompt} disabled={busy} onClick={() => ask(prompt)} className="rounded-full border border-[#E7E1F3] px-3 py-2 text-sm text-[#7567BC] disabled:opacity-50">{prompt}</button>)}</div>
    <div className="mt-4 max-h-[480px] space-y-4 overflow-y-auto" aria-live="polite">{history.map((item, index) => <article key={index} className="rounded-xl bg-[#F8F6FD] p-4">
      <p className="font-semibold">{item.question}</p><p className="mt-1 text-xs text-[#817B9D]">{item.reply.mode === 'ai' ? 'AI · phân tích dựa trên dữ liệu backend' : 'Dữ liệu nội bộ'} · {item.reply.scope}</p><p className="mt-3 whitespace-pre-wrap text-sm leading-6">{item.reply.answer}</p>
      {item.reply.validation && item.reply.validation.status !== 'not_applicable' && <div className={`mt-3 rounded-lg px-3 py-2 text-xs ${item.reply.validation.status === 'passed' ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-900'}`}>
        <strong>{item.reply.validation.status === 'passed' ? 'Đối chiếu số học nội bộ đã đạt' : 'Có số liệu cần đối chiếu lại'}</strong>
        <span className="ml-2">{item.reply.validation.passed_checks}/{item.reply.validation.total_checks} phép kiểm tra đạt</span><p className="mt-1 opacity-80">Chỉ kiểm tra tính nhất quán của dữ liệu đã lưu, không thay thế đối chiếu OCR với hóa đơn gốc.</p>
        {item.reply.validation.status === 'warning' && <ul className="mt-2 list-disc pl-4">{item.reply.validation.checks.filter(check => !check.passed).map(check => <li key={check.code}>{check.label}: dự kiến {check.expected}, thực tế {check.actual}</li>)}</ul>}
      </div>}
      {item.reply.evidence && item.reply.evidence.length > 0 && <details className="mt-3 rounded-lg border border-[#E7E1F3] bg-white p-3 text-sm"><summary className="cursor-pointer font-medium text-[#7567BC]">Số liệu backend đã truy vấn và kiểm chứng</summary>
        {item.reply.evidence.map((evidence, evidenceIndex) => <div key={`${evidence.title}-${evidenceIndex}`} className="mt-3 overflow-x-auto"><p className="mb-2 font-semibold">{evidence.title}</p><table className="w-full border-collapse text-left text-xs"><thead><tr>{evidence.columns.map(column => <th key={column} className="border-b border-[#E7E1F3] px-2 py-2">{column}</th>)}</tr></thead><tbody>{evidence.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex} className="border-b border-[#F0ECF7] px-2 py-2">{cell ?? '—'}</td>)}</tr>)}</tbody></table></div>)}
      </details>}
      {item.reply.tools_used && item.reply.tools_used.length > 0 && <p className="mt-2 text-xs text-[#817B9D]">Công cụ đã dùng: {item.reply.tools_used.join(', ')}</p>}
      {item.reply.sources.length > 0 && <details className="mt-3 text-sm"><summary className="cursor-pointer text-[#7567BC]">Hóa đơn để đối chiếu ({item.reply.sources.length})</summary><p className="mt-2 text-xs text-[#817B9D]">{item.reply.source_note}</p><ul className="mt-2 space-y-1">{item.reply.sources.map(source => <li key={source.invoice_id}><a href={getInvoiceFileUrl(source.invoice_id)} target="_blank" rel="noreferrer" className="underline">{source.invoice_number || `Hóa đơn #${source.invoice_id}`}{source.seller_name ? ` · ${source.seller_name}` : ''}{source.invoice_date ? ` · ${source.invoice_date}` : ''}{source.source_page ? ` · Trang ${source.source_page}` : ''}</a></li>)}</ul></details>}
    </article>)}</div>
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    <form className="mt-4 flex flex-col gap-3 sm:flex-row" onSubmit={event => { event.preventDefault(); void ask() }}><label className="flex-1"><span className="sr-only">Câu hỏi</span><textarea value={question} maxLength={2000} onChange={e => setQuestion(e.target.value)} placeholder="Nhập câu hỏi về hóa đơn..." rows={2} className="w-full rounded-xl border border-[#E7E1F3] p-3 text-sm" /></label><button disabled={busy || !question.trim()} className="rounded-xl bg-[#8C7BEF] px-5 py-3 text-sm font-medium text-white disabled:opacity-50">{busy ? 'Đang trả lời...' : 'Gửi câu hỏi'}</button></form>
  </section>
}
