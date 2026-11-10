import { Info } from 'lucide-react'
import InvoicesPage from './InvoicesPage'

/** Presentation-only wrapper. Existing OCR/import/delete flows remain untouched. */
export default function InvoicesWorkspacePage() {
  return <div className="invoice-page space-y-4">
    <div className="flex flex-wrap items-start gap-3 rounded-2xl border border-[#31516b] bg-[#112740] px-4 py-3 text-sm text-[#b6d4e7]">
      <Info size={18} className="mt-0.5 shrink-0 text-[#5fdcf0]" />
      <div className="flex-1"><strong className="text-[#dff5ff]">Hóa đơn chưa được phân loại theo hướng thu / chi.</strong> Người bán thuộc nhiều ngành nghề không tự chứng minh đây là hóa đơn doanh nghiệp đã chi. Trong phiên bản hiện tại, chúng tôi quản lý chứng từ và tổng giá trị, chưa xác định doanh thu hoặc chi phí.</div>
    </div>
    <InvoicesPage />
  </div>
}
