import { Info } from 'lucide-react'
import InvoicesPage from './InvoicesPage'

/** Presentation-only wrapper. Existing OCR/import/delete flows remain untouched. */
export default function InvoicesWorkspacePage() {
  return <div className="invoice-page space-y-4">
    <div className="flex flex-wrap items-start gap-3 rounded-2xl border border-[#31516b] bg-[#112740] px-4 py-3 text-sm text-[#b6d4e7]">
      <Info size={18} className="mt-0.5 shrink-0 text-[#5fdcf0]" />
      <div className="flex-1"><strong className="text-[#dff5ff]">Phân loại hóa đơn theo Mua vào / Bán ra / Chưa phân loại.</strong> Mỗi hóa đơn được gán mặc định “Chưa phân loại”. Bạn có thể xác nhận hướng giao dịch cho từng hóa đơn bằng hộp chọn bên dưới. Giá trị mua vào không đồng nghĩa đã thanh toán; giá trị bán ra không đồng nghĩa đã thu tiền.</div>
    </div>
    <InvoicesPage />
  </div>
}
