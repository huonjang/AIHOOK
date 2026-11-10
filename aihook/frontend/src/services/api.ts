// Cùng origin trong dev qua Vite proxy; có thể override ở production.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')

export function getInvoiceFileUrl(id: number | string): string {
  return `${API_BASE_URL}/api/invoices/${encodeURIComponent(String(id))}/file`
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options)
  } catch {
    throw new Error('Không thể kết nối máy chủ. Vui lòng thử lại.')
  }

  const contentType = response.headers.get('content-type') || ''
  const data: unknown = contentType.includes('application/json')
    ? await response.json()
    : null

  if (!response.ok) {
    let message = `HTTP ${response.status}`
    if (data && typeof data === 'object' && 'detail' in data) {
      const detail = data.detail
      if (typeof detail === 'string') message = detail
      else if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') {
        message = detail.message
      }
    }
    throw new ApiError(message, response.status)
  }
  return data as T
}

export interface Invoice {
  id: number
  filename: string
  size: number
  status: string
  source_file?: string | null
  source_page?: number | null
  processing_error?: string
  created_at: string
}

export interface InvoiceAnalysis {
  invoice_id: number
  status?: string
  invoice_number: string | null
  invoice_date: string | null
  seller_name: string | null
  seller_tax_code: string | null
  total_amount: string | null
  raw_text: string
  analyzed_at: string | null
  verification_status: string
  ocr_fields?: {
    invoice_number: string | null
    invoice_date: string | null
    seller_name: string | null
    total_amount: string | null
  }
  validation?: { eligible: boolean; errors: string[]; warnings: string[] }
  auto_confirmation?: { eligible: boolean; errors: string[]; warnings: string[] }
}

export interface InvoiceSummary {
  business_id: number
  start_date: string | null
  end_date: string | null
  invoice_count: number
  total_amount: string
  currency: string
  business_name: string
}

export interface AnalyticsDashboard {
  business_id: number
  start_date: string | null
  end_date: string | null
  currency: string
  overview: { invoice_count: number; total_amount: string; average_amount: string; supplier_count: number; undated_count: number }
  monthly: { month: string; invoice_count: number; total_amount: string }[]
  suppliers: { seller_name: string; seller_tax_code: string | null; invoice_count: number; total_amount: string }[]
}

export interface ChatReply {
  answer: string; mode: string; scope: string; source_note: string
  sources: { invoice_id: number; invoice_number: string | null; total_amount: string; source_page: number | null }[]
}

export const api = {
  getChatStatus: () => request<{ ai_configured: boolean }>('/api/chat/status'),
  askQuestion: (message: string, start: string, end: string, useAI: boolean) => request<ChatReply>('/api/chat', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, start_date: start || null, end_date: end || null, use_ai: useAI }),
  }),
  getAnalytics: (start = '', end = '', signal?: AbortSignal) => {
    const params = new URLSearchParams()
    if (start) params.set('start_date', start)
    if (end) params.set('end_date', end)
    return request<AnalyticsDashboard>(`/api/analytics/dashboard?${params}`, { signal })
  },
  getInvoices: () => request<Invoice[]>('/api/invoices'),

  uploadInvoice: (file: File, mode = 'single') => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('import_mode', mode)
    return request<Invoice | { invoices: Invoice[] }>('/api/invoices/upload', { method: 'POST', body: formData })
  },

  splitInvoice: (id: number) => request<{ invoices: Invoice[] }>(`/api/invoices/${id}/split-pages`, { method: 'POST' }),

  analyzeInvoice: (id: number | string) =>
    request<InvoiceAnalysis>(`/api/invoices/${id}/analyze`, { method: 'POST' }),

  getInvoiceAnalysis: (id: number | string) =>
    request<InvoiceAnalysis>(`/api/invoices/${id}/analysis`),

  deleteInvoice: (id: number | string) =>
    request<{ message: string }>(`/api/invoices/${id}`, { method: 'DELETE' }),

  getInvoiceSummary: (startDate: string, endDate: string, businessId = 1) => {
    const params = new URLSearchParams({
      business_id: String(businessId), start_date: startDate, end_date: endDate,
    })
    return request<InvoiceSummary>(`/api/ai-data/summary?${params}`)
  },

  getInvoiceSummaryAll: (businessId = 1) =>
    request<InvoiceSummary>(`/api/ai-data/summary?business_id=${businessId}`),
}
