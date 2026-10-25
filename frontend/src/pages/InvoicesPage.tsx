
import { useState } from 'react'
import { Upload, Search } from 'lucide-react'

export default function InvoicesPage() {
  const [keyword, setKeyword] = useState('')

  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm text-slate-500">
          Workspace / Hóa đơn
        </p>
        <h2 className="mt-2 text-3xl font-bold">
          Quản lý hóa đơn
        </h2>
        <p className="mt-2 text-sm text-slate-500">
          Quản lý và theo dõi quá trình xử lý hóa đơn.
        </p>
      </header>

      <div className="flex flex-wrap gap-3">
        <label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border bg-white px-4 py-3 sm:max-w-md">
          <Search size={18} className="text-slate-400" />
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="Tìm mã hoặc nhà cung cấp..."
            className="w-full bg-transparent text-sm outline-none"
          />
        </label>

        <label className="flex cursor-pointer items-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-medium text-white hover:bg-indigo-700">
          <Upload size={18} />
          Chọn hóa đơn
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            multiple
            className="hidden"
            onChange={(event) => {
              const files = event.target.files

              if (files && files.length > 0) {
                alert(
                  `Đã chọn ${files.length} tệp. Chức năng tải lên sẽ được phát triển sau.`,
                )
              }
            }}
          />
        </label>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-8 text-center">
        <Upload
          size={36}
          className="mx-auto text-indigo-500"
        />

        <h3 className="mt-4 font-semibold">
          Chưa có hóa đơn
        </h3>

        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">
          Chọn tệp để thử giao diện. Chức năng OCR và lưu hóa đơn
          sẽ được kết nối với backend ở giai đoạn tiếp theo.
        </p>
      </section>

      {keyword && (
        <p className="text-sm text-slate-500">
          Từ khóa tìm kiếm: {keyword}
        </p>
      )}
    </div>
  )
}
