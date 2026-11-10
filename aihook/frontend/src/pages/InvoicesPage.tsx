import { api, ApiError, getInvoiceFileUrl, type Invoice, type InvoiceAnalysis } from '../services/api'
import { useEffect, useState } from 'react'
import {
  Upload,
  Search,
  FileText,
  Image as ImageIcon,
  X,
  Trash2,
  Eye,
  AlertCircle,
  Clock3,
  ScanSearch,
  LoaderCircle,
} from 'lucide-react'

const MAX_FILE_SIZE = 10 * 1024 * 1024
const ACCEPTED_TYPES = ['application/pdf', 'image/png', 'image/jpeg']
const ACCEPTED_EXTENSIONS = /\.(pdf|png|jpe?g)$/i

type InvoiceFile = File | {
  name: string
  size: number
  type: string
  lastModified: number
}

type DisplayInvoice = {
  id: string
  serverId?: number
  sourceFile?: string | null
  file: InvoiceFile
  status: string
  addedAt: string | Date
}

function displayStatus(status: string): string {
  if (status === 'confirmed') return 'Đã ghi nhận'
  if (status === 'needs_review') return 'Chưa đủ điều kiện'
  if (status === 'uploaded') return 'Đã tải lên'
  return status
}

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function getFileType(file: InvoiceFile) {
  if (file.type === 'application/pdf' || /\.pdf$/i.test(file.name)) {
    return 'PDF'
  }
  return 'IMAGE'
}

function getStatusStyle(status: string) {
  if (status === 'Lỗi đầu vào' || status === 'Lỗi tải lên') {
    return 'bg-rose-50 text-rose-700'
  }
  if (status === 'Đang tải lên') {
    return 'bg-amber-50 text-amber-700'
  }
  if (status === 'Đã tải lên' || status === 'Đã ghi nhận') {
    return 'bg-emerald-50 text-emerald-700'
  }
  return 'bg-[#F0EDFA] text-[#7567BC]'
}

function toDisplayInvoice(item: Invoice): DisplayInvoice {
  return { id: String(item.id), serverId: item.id, sourceFile: item.source_file,
    file: { name: item.filename, size: item.size, type: item.filename.includes('.pdf') ? 'application/pdf' : 'image/png', lastModified: 0 },
    status: displayStatus(item.status), addedAt: item.created_at }
}

export default function InvoicesPage() {
  const [importMode, setImportMode] = useState('single')
  const [splittingId, setSplittingId] = useState<number | null>(null)
  const [keyword, setKeyword] = useState('')
  const [invoices, setInvoices] = useState<DisplayInvoice[]>([])
  const [errors, setErrors] = useState<string[]>([])
  const [preview, setPreview] = useState<{
    url: string
    name: string
    type: string
    revokeUrl: boolean
  } | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isDeleting, setIsDeleting] = useState<string | null>(null)
  const [analyzingId, setAnalyzingId] = useState<string | null>(null)
  const [analysisResult, setAnalysisResult] = useState<InvoiceAnalysis | null>(null)

  // Tải danh sách hóa đơn qua api.getInvoices()
  useEffect(() => {
    let cancelled = false

    async function loadInvoices() {
      setIsLoading(true)

      try {
        const data = await api.getInvoices()

        if (cancelled) return

        const savedInvoices: DisplayInvoice[] = data.map((item: Invoice) => ({
          id: String(item.id),
          serverId: item.id,
          sourceFile: item.source_file,
          file: {
            name: item.filename,
            size: item.size,
            type: /\.pdf$/i.test(item.filename)
              ? 'application/pdf'
              : /\.png$/i.test(item.filename)
                ? 'image/png'
                : 'image/jpeg',
            lastModified: 0,
          },
          status: displayStatus(item.status),
          addedAt: item.created_at,
        }))

        setInvoices((current) => {
          const localUploads = current.filter((invoice) => !invoice.serverId)

          return [
            ...savedInvoices,
            ...localUploads.filter(
              (local) =>
                !savedInvoices.some(
                  (saved: DisplayInvoice) =>
                    saved.file.name === local.file.name &&
                    saved.file.size === local.file.size,
                ),
            ),
          ]
        })
      } catch (error) {
        if (!cancelled) {
          setErrors((current) => [
            ...current,
            `Không thể tải danh sách hóa đơn: ${
              error instanceof Error ? error.message : 'Lỗi không xác định'
            }`,
          ])
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    loadInvoices()

    return () => {
      cancelled = true
    }
  }, [])

  // Giải phóng URL Object khi tắt preview tệp local
  useEffect(() => {
    return () => {
      if (preview?.revokeUrl && preview.url) {
        URL.revokeObjectURL(preview.url)
      }
    }
  }, [preview])

  // Mở thông tin trích xuất hoặc nhận diện lại
  const analyzeInvoice = async (invoice: DisplayInvoice, retry = false) => {
    const invoiceId = invoice.serverId

    if (!invoiceId) {
      setErrors((current) => [
        ...current,
        'Hóa đơn chưa được lưu trên máy chủ.',
      ])
      return
    }

    setAnalyzingId(invoice.id)

    try {
      // Mở bản lưu trước, chỉ chạy OCR nếu đây là lần phân tích đầu tiên.
      // Chỉ chạy lại OCR khi người dùng yêu cầu cho bản chưa ghi nhận.
      let result: InvoiceAnalysis
      try {
        result = retry ? await api.analyzeInvoice(invoiceId) : await api.getInvoiceAnalysis(invoiceId)
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 404) throw error
        result = await api.analyzeInvoice(invoiceId)
      }

      setInvoices((current) =>
        current.map((item) =>
          String(item.serverId) === String(invoiceId)
            ? {
                ...item,
                status:
                  result.verification_status === 'confirmed'
                    ? 'Đã ghi nhận'
                    : 'Chưa đủ điều kiện',
              }
            : item,
        ),
      )

      setAnalysisResult(result)
    } catch (error) {
      setErrors((current) => [
        ...current,
        `Không thể phân tích ${invoice.file.name}: ${
          error instanceof Error ? error.message : 'Lỗi không xác định'
        }`,
      ])
    } finally {
      setAnalyzingId(null)
    }
  }

  // Tải lên tệp qua api.uploadInvoice()
  const handleFiles = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const input = event.target
    const selectedFiles = Array.from(input.files || [])

    input.value = ''

    const newErrors: string[] = []
    const newInvoices: (DisplayInvoice & { file: File })[] = []

    selectedFiles.forEach((file) => {
      const validExtension = ACCEPTED_EXTENSIONS.test(file.name)
      const validType =
        ACCEPTED_TYPES.includes(file.type) ||
        (file.type === '' && validExtension)

      if (!validExtension || !validType) {
        newErrors.push(`${file.name}: Chỉ chấp nhận PDF, PNG hoặc JPG.`)
        return
      }

      if (file.size === 0) {
        newErrors.push(`${file.name}: Tệp rỗng, vui lòng chọn tệp khác.`)
        return
      }

      if (file.size > MAX_FILE_SIZE) {
        newErrors.push(`${file.name}: Dung lượng vượt quá 10 MB.`)
        return
      }

      const duplicate =
        invoices.some(
          (invoice) =>
            invoice.file.name === file.name &&
            invoice.file.size === file.size &&
            invoice.file.lastModified === file.lastModified,
        ) ||
        newInvoices.some(
          (invoice) =>
            invoice.file.name === file.name &&
            invoice.file.size === file.size &&
            invoice.file.lastModified === file.lastModified,
        )

      if (duplicate) {
        newErrors.push(`${file.name}: Tệp đã có trong danh sách.`)
        return
      }

      newInvoices.push({
        id: crypto.randomUUID(),
        file,
        status: 'Đang tải lên',
        addedAt: new Date(),
      })
    })

    setInvoices((current) => [...current, ...newInvoices])
    setErrors(newErrors)

    for (const invoice of newInvoices) {
      try {
        const response = await api.uploadInvoice(invoice.file, importMode)
        if ('invoices' in response) {
          setInvoices(current => [...current.filter(item => item.id !== invoice.id), ...response.invoices.map(toDisplayInvoice)])
          response.invoices.forEach(item => { if (item.processing_error) newErrors.push(`${item.filename}: ${item.processing_error}`) })
          continue
        }
        const result = response
        if (result.processing_error) newErrors.push(`${invoice.file.name}: ${result.processing_error}`)

        setInvoices((current) =>
          current.map((item) =>
            item.id === invoice.id
              ? {
                  ...item,
                  serverId: result.id,
                  status: displayStatus(result.status),
                }
              : item,
          ),
        )
      } catch (error) {
        setInvoices((current) =>
          current.map((item) =>
            item.id === invoice.id
              ? { ...item, status: 'Lỗi tải lên' }
              : item,
          ),
        )

        newErrors.push(
          `${invoice.file.name}: ${
            error instanceof Error
              ? error.message
              : 'Không thể kết nối backend.'
          }`,
        )
      }
    }

    setErrors(newErrors)
  }

  const splitInvoice = async (invoice: DisplayInvoice) => {
    if (!invoice.serverId || splittingId !== null) return
    if (!window.confirm('Chỉ tách khi MỖI TRANG là một hóa đơn độc lập. Bản ghi cũ sẽ được thay bằng các hóa đơn theo trang, không cộng trùng. Tiếp tục?')) return
    setSplittingId(invoice.serverId)
    try {
      const result = await api.splitInvoice(invoice.serverId)
      setInvoices(current => [...current.filter(item => item.id !== invoice.id), ...result.invoices.map(toDisplayInvoice)])
      setErrors(current => [...current, ...result.invoices.filter(item => item.processing_error).map(item => `${item.filename}: ${item.processing_error}`)])
    } catch (error) { setErrors(current => [...current, error instanceof Error ? error.message : 'Không thể tách PDF.']) }
    finally { setSplittingId(null) }
  }

  // Xóa hóa đơn qua api.deleteInvoice()
  const removeInvoice = async (id: string) => {
    const invoice = invoices.find((item) => item.id === id)
    if (!invoice) return

    if (!invoice.serverId) {
      setInvoices((current) => current.filter((item) => item.id !== id))
      return
    }

    setIsDeleting(id)

    try {
      await api.deleteInvoice(invoice.serverId)

      setInvoices((current) => current.filter((item) => item.id !== id))

      if (
        preview?.url ===
        getInvoiceFileUrl(invoice.serverId)
      ) {
        setPreview(null)
      }
    } catch (error) {
      setErrors((current) => [
        ...current,
        `Không thể xóa ${invoice.file.name}: ${
          error instanceof Error ? error.message : 'Lỗi không xác định'
        }`,
      ])
    } finally {
      setIsDeleting(null)
    }
  }

  // Mở modal xem trước
  const openPreview = (invoice: DisplayInvoice) => {
    const file = invoice.file

    if (file instanceof File) {
      const url = URL.createObjectURL(file)
      setPreview({
        url,
        name: file.name,
        type: getFileType(file),
        revokeUrl: true,
      })
      return
    }

    if (invoice.serverId) {
      setPreview({
        url: getInvoiceFileUrl(invoice.serverId),
        name: file.name,
        type: getFileType(file),
        revokeUrl: false,
      })
      return
    }

    setErrors((current) => [
      ...current,
      `Không thể xem trước ${file?.name ?? 'hóa đơn'}: không tìm thấy file.`,
    ])
  }

  const closePreview = () => {
    setPreview(null)
  }

  const filteredInvoices = invoices.filter((invoice) =>
    invoice.file.name.toLowerCase().includes(keyword.trim().toLowerCase()),
  )

  const imageCount = invoices.filter(
    (invoice) => getFileType(invoice.file) === 'IMAGE',
  ).length

  const pdfCount = invoices.length - imageCount

  return (
    <div className="space-y-6">
      {/* Header */}
      <header>
        <p className="text-sm text-[#817B9D]">Workspace / Hóa đơn</p>
        <h2 className="mt-2 text-3xl font-bold tracking-tight text-[#302B4A]">
          Quản lý hóa đơn
        </h2>
        <p className="mt-2 text-sm text-[#817B9D]">
          Tải lên, tìm kiếm và theo dõi các hóa đơn cần xử lý.
        </p>
      </header>

      {/* Summary */}
      <section className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-[#E7E3F0] bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-sm text-[#817B9D]">Tổng hóa đơn</p>
            <FileText size={19} className="text-[#8B80E8]" />
          </div>
          <p className="mt-3 text-2xl font-bold text-[#302B4A]">
            {invoices.length}
          </p>
        </div>

        <div className="rounded-2xl border border-[#E7E3F0] bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-sm text-[#817B9D]">Hóa đơn PDF</p>
            <FileText size={19} className="text-[#8B80E8]" />
          </div>
          <p className="mt-3 text-2xl font-bold text-[#302B4A]">
            {pdfCount}
          </p>
        </div>

        <div className="rounded-2xl border border-[#E7E3F0] bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-sm text-[#817B9D]">Ảnh hóa đơn</p>
            <ImageIcon size={19} className="text-[#8B80E8]" />
          </div>
          <p className="mt-3 text-2xl font-bold text-[#302B4A]">
            {imageCount}
          </p>
        </div>
      </section>

      <section className="rounded-xl border border-[#E7E3F0] bg-white p-4 text-sm">
        <label className="font-medium">Cấu trúc PDF tải lên
          <select value={importMode} onChange={event => setImportMode(event.target.value)} className="ml-3 rounded-lg border p-2">
            <option value="single">Một hóa đơn / tệp (có thể nhiều trang)</option>
            <option value="per_page">Mỗi trang là một hóa đơn độc lập</option>
          </select>
        </label>
      </section>
      {/* Search and upload */}
      <section className="flex flex-col gap-3 sm:flex-row">
        <label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-[#E7E3F0] bg-white px-4 py-3 sm:max-w-md">
          <Search size={18} className="shrink-0 text-[#A09AB8]" />
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="Tìm theo tên tệp..."
            className="w-full bg-transparent text-sm text-[#302B4A] outline-none placeholder:text-[#AAA5BD]"
          />
        </label>

        <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl bg-[#8B80E8] px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-[#796DDA]">
          <Upload size={18} />
          Chọn hóa đơn
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
            multiple
            className="hidden"
            onChange={handleFiles}
          />
        </label>
      </section>

      {/* Validation errors */}
      {errors.length > 0 && (
        <section
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-4"
        >
          <div className="flex items-center gap-2 font-medium text-rose-800">
            <AlertCircle size={18} />
            Không thể thêm một số tệp
          </div>

          <ul className="mt-2 space-y-1 text-sm text-rose-700">
            {errors.map((error, index) => (
              <li key={`${error}-${index}`}>{error}</li>
            ))}
          </ul>

          <button
            type="button"
            onClick={() => setErrors([])}
            className="mt-3 text-sm font-medium text-rose-800 underline"
          >
            Đóng thông báo
          </button>
        </section>
      )}

      {/* File list */}
      <section className="overflow-hidden rounded-2xl border border-[#E7E3F0] bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#EEEAF5] px-5 py-4">
          <div>
            <h3 className="font-semibold text-[#302B4A]">
              Danh sách hóa đơn
            </h3>
            <p className="mt-1 text-xs text-[#817B9D]">
              {filteredInvoices.length} tệp được hiển thị
            </p>
          </div>

          <span className="rounded-full bg-[#F0EDFA] px-3 py-1 text-xs font-medium text-[#7567BC]">
            Giới hạn 10 MB/tệp
          </span>
        </div>

        {isLoading ? (
          <div className="px-6 py-14 text-center text-sm text-[#817B9D]">
            Đang tải danh sách hóa đơn...
          </div>
        ) : filteredInvoices.length === 0 ? (
          <div className="px-6 py-14 text-center">
            <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-[#F0EDFA]">
              {keyword ? (
                <Search size={25} className="text-[#8B80E8]" />
              ) : (
                <Upload size={25} className="text-[#8B80E8]" />
              )}
            </div>

            <h4 className="mt-4 font-semibold text-[#302B4A]">
              {keyword
                ? 'Không tìm thấy hóa đơn phù hợp'
                : 'Chưa có hóa đơn'}
            </h4>

            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#817B9D]">
              {keyword
                ? 'Thử một từ khóa khác hoặc xóa nội dung tìm kiếm.'
                : 'Chọn tệp PDF, PNG hoặc JPG để bắt đầu. Tệp sẽ được hiển thị trong danh sách để bạn xem trước.'}
            </p>

            {keyword && (
              <button
                type="button"
                onClick={() => setKeyword('')}
                className="mt-4 text-sm font-medium text-[#7567BC] hover:underline"
              >
                Xóa từ khóa
              </button>
            )}
          </div>
        ) : (
          <div className="divide-y divide-[#EEEAF5]">
            {filteredInvoices.map((invoice) => {
              const isPdf = getFileType(invoice.file) === 'PDF'

              return (
                <div
                  key={invoice.id}
                  className="flex flex-col gap-4 px-5 py-4 transition-colors hover:bg-[#FBFAFE] sm:flex-row sm:items-center"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-[#F0EDFA]">
                      {isPdf ? (
                        <FileText size={21} className="text-[#7567BC]" />
                      ) : (
                        <ImageIcon size={21} className="text-[#7567BC]" />
                      )}
                    </div>

                    <div className="min-w-0 flex-1">
                      <p
                        className="truncate text-sm font-semibold text-[#302B4A]"
                        title={invoice.file.name}
                      >
                        {invoice.file.name}
                      </p>

                      <p className="mt-1 text-xs text-[#817B9D]">
                        {isPdf ? 'PDF' : 'Hình ảnh'}
                        {' · '}
                        {formatSize(invoice.file.size)}
                      </p>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 sm:justify-end">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium ${getStatusStyle(
                        invoice.status,
                      )}`}
                    >
                      <Clock3 size={13} />
                      {invoice.status}
                    </span>

                    {/* Nút Xem trước */}
                    <button
                      type="button"
                      onClick={() => openPreview(invoice)}
                      title="Xem trước tệp"
                      aria-label={`Xem trước ${invoice.file.name}`}
                      className="rounded-lg border border-[#E7E3F0] p-2 text-[#7567BC] transition-colors hover:bg-[#F0EDFA]"
                    >
                      <Eye size={17} />
                    </button>

                    {/* Nút Phân tích OCR */}
                    <button
                      type="button"
                      onClick={() => analyzeInvoice(invoice)}
                      disabled={analyzingId === invoice.id || !invoice.serverId}
                      title="Xem kết quả đã lưu hoặc phân tích OCR nếu chưa có"
                      className="inline-flex items-center gap-2 rounded-lg border border-[#DCD5FF] px-3 py-2 text-sm font-medium text-[#7465D8] transition-colors hover:bg-[#F3F0FF] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {analyzingId === invoice.id ? (
                        <LoaderCircle size={16} className="animate-spin" />
                      ) : (
                        <ScanSearch size={16} />
                      )}
                      {analyzingId === invoice.id
                        ? 'Đang phân tích...'
                        : 'Phân tích / Xem'}
                    </button>

                    {isPdf && invoice.serverId && !invoice.sourceFile && <button type="button" onClick={() => splitInvoice(invoice)} disabled={splittingId !== null} className="rounded-lg border p-2 text-sm text-[#7567BC] disabled:opacity-50">{splittingId === invoice.serverId ? 'Đang tách...' : 'Tách PDF theo trang'}</button>}
                    {/* Nút Xóa */}
                    <button
                      type="button"
                      onClick={() => removeInvoice(invoice.id)}
                      disabled={isDeleting === invoice.id}
                      title="Xóa tệp"
                      aria-label={`Xóa ${invoice.file.name}`}
                      className="rounded-lg border border-[#F0DDE0] p-2 text-rose-600 transition-colors hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <Trash2 size={17} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {invoices.length > 0 && (
          <div className="border-t border-[#EEEAF5] px-5 py-3">
            <p className="text-xs leading-5 text-[#817B9D]">
              Danh sách hóa đơn được đồng bộ từ máy chủ và lưu trong SQLite.
            </p>
          </div>
        )}
      </section>

      {/* Thông tin trích xuất chỉ đọc */}
      {analysisResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-[#E9E4F5] p-5">
              <div>
                <h2 className="text-lg font-bold text-[#302653]">
                  Thông tin trích xuất
                </h2>
                <p className="mt-1 text-sm text-[#817B9D]">
                  Dữ liệu chỉ đọc từ hóa đơn gốc; hệ thống tự động ghi nhận khi đạt kiểm tra.
                </p>
              </div>

              <button
                type="button"
                onClick={() => setAnalysisResult(null)}
                className="rounded-lg p-2 text-[#817B9D] hover:bg-[#F4F1FC]"
                aria-label="Đóng kết quả"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4 p-5">
              {/* Kết quả OCR ban đầu, chỉ đọc */}
              <section className="space-y-3">
                <h3 className="font-semibold text-[#302653]">
                  Kết quả OCR nhận diện
                </h3>

                <p className="text-sm text-[#817B9D]">
                  Kết quả kiểm tra dữ liệu không chứng minh tính xác thực pháp lý của hóa đơn.
                </p>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {[
                    ['Mã hóa đơn', analysisResult.invoice_number],
                    ['Ngày lập', analysisResult.invoice_date],
                    ['Đơn vị bán', analysisResult.seller_name],
                    ['Mã số thuế', analysisResult.seller_tax_code],
                    ['Tổng tiền', analysisResult.total_amount],
                  ].map(([label, value]) => (
                    <div
                      key={String(label)}
                      className="rounded-xl border border-[#E9E4F5] bg-[#FAF9FF] p-4"
                    >
                      <p className="text-sm text-[#817B9D]">{label}</p>

                      <p className="mt-2 break-words font-semibold text-[#302653]">
                        {value !== null && value !== undefined && String(value).trim() !== ''
                          ? String(value)
                          : 'Chưa trích xuất được'}
                      </p>
                    </div>
                  ))}
                </div>
              </section>

              <div className="border-t border-[#E9E4F5]" />

              <div className="rounded-xl bg-[#FFF8E8] p-4 text-sm leading-6 text-[#805D19]">
                <p className="font-semibold">{displayStatus(analysisResult.verification_status)}</p>
                {analysisResult.validation?.errors.map((message) => <p key={message}>{message}</p>)}
                {analysisResult.validation?.warnings.map((message) => <p key={message}>{message}</p>)}
                {analysisResult.verification_status !== 'confirmed' && <p>Hãy nhận diện lại hoặc tải bản rõ hơn tại khu vực tải hóa đơn.</p>}
              </div>

              <details className="rounded-xl border border-[#E9E4F5] p-4">
                <summary className="cursor-pointer font-medium text-[#51427F]">
                  Xem văn bản OCR gốc
                </summary>
                <pre className="mt-3 whitespace-pre-wrap break-words text-xs leading-5 text-[#514B65]">
                  {analysisResult.raw_text || 'Không có văn bản.'}
                </pre>
              </details>
            </div>

            {/* Footer modal có đầy đủ các nút thao tác */}
            <div className="flex flex-wrap justify-end gap-3 border-t border-[#E9E4F5] p-4">
              <button
                type="button"
                onClick={() => setAnalysisResult(null)}
                className="rounded-xl border border-[#E7E3F0] px-4 py-2.5 text-sm font-medium text-[#51427F] hover:bg-[#F7F5FC]"
              >
                Đóng
              </button>

              <a href={getInvoiceFileUrl(analysisResult.invoice_id)} target="_blank" rel="noreferrer" className="rounded-xl border px-4 py-2.5 text-sm">Xem bản gốc</a>
              {analysisResult.verification_status !== 'confirmed' && (
                <button type="button" disabled={analyzingId !== null} className="rounded-xl bg-[#8C7BEF] px-4 py-2.5 text-sm text-white disabled:opacity-50" onClick={() => {
                  const invoice = invoices.find((item) => item.serverId === analysisResult.invoice_id)
                  if (invoice) void analyzeInvoice(invoice, true)
                }}>{analyzingId ? 'Đang xử lý...' : 'Nhận diện lại'}</button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal Preview hóa đơn */}
      {preview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#211B38]/50 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closePreview()
            }
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-label={`Xem trước ${preview.name}`}
            className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-[#E7E3F0] bg-white shadow-xl"
          >
            <div className="flex items-center justify-between gap-3 border-b border-[#EEEAF5] px-5 py-4">
              <div className="min-w-0">
                <h3 className="font-semibold text-[#302B4A]">
                  Xem trước hóa đơn
                </h3>
                <p className="mt-1 truncate text-xs text-[#817B9D]">
                  {preview.name}
                </p>
              </div>

              <button
                type="button"
                onClick={closePreview}
                aria-label="Đóng xem trước"
                className="shrink-0 rounded-lg p-2 text-[#817B9D] hover:bg-[#F0EDFA]"
              >
                <X size={20} />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-auto bg-[#F7F6FC] p-4">
              {preview.type === 'PDF' ? (
                <iframe
                  title={`Xem trước ${preview.name}`}
                  src={preview.url}
                  className="h-[65vh] w-full rounded-lg border border-[#E7E3F0] bg-white"
                />
              ) : (
                <img
                  src={preview.url}
                  alt={`Xem trước ${preview.name}`}
                  className="mx-auto max-h-[65vh] max-w-full rounded-lg object-contain"
                />
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  )
}