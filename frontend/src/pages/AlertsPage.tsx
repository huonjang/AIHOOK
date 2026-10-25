import { ShieldAlert } from 'lucide-react'

export default function AlertsPage() {
  return (
    <section className="rounded-2xl border bg-white p-8">
      <ShieldAlert size={36} className="text-amber-500" />
      <h2 className="mt-4 text-3xl font-bold">Cảnh báo bất thường</h2>
      <p className="mt-3 max-w-2xl leading-7 text-slate-500">
        Đây sẽ là tính năng mở rộng của AITHOOK. Hệ thống sẽ kiểm tra dữ liệu
        trích xuất từ hóa đơn bằng các quy tắc như tổng tiền không khớp,
        trường bắt buộc bị thiếu hoặc hóa đơn có thông tin trùng lặp.
        Các cảnh báo cần được người dùng xác minh trước khi đưa ra kết luận.
      </p>
      <span className="mt-5 inline-block rounded-full bg-amber-50 px-3 py-2 text-xs text-amber-700">
        Chưa kết nối bộ kiểm tra
      </span>
    </section>
  )
}