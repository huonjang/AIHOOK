
const API_BASE_URL = 'http://127.0.0.1:8000'

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, options)

  const contentType = response.headers.get('content-type') || ''
  const data = contentType.includes('application/json')
    ? await response.json()
    : null

  if (!response.ok) {
    const detail = data?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : detail?.message || `HTTP ${response.status}`

    throw new Error(message)
  }

  return data as T
}

export interface Invoice {
  id: number
  filename: string
  size: number
  status: string
  created_at: string
}

export interface InvoiceAnalysis {
  invoice_id: number | string
  invoice_number: string | null
  invoice_date: string | null
  seller_name: string | null
  total_amount: string | number | null
  raw_text: string
  analyzed_at?: string
  verification_status?: string
  auto_confirmation?: {
    eligible: boolean
    errors: string[]
    warnings: string[]
  }
}

export interface InvoiceReview {
  invoice_number: string
  invoice_date: string
  seller_name: string
  seller_tax_code: string
  total_amount: string
}

export const api = {
  getInvoices: () =>
    request<Invoice[]>('/api/invoices'),

  uploadInvoice: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)

    return request<Invoice>('/api/invoices/upload', {
      method: 'POST',
      body: formData,
    })
  },

  analyzeInvoice: (id: number | string) =>
    request<InvoiceAnalysis>(
      `/api/invoices/${id}/analyze`,
      { method: 'POST' },
    ),

  getInvoiceAnalysis: (id: number | string) =>
    request<InvoiceAnalysis>(`/api/invoices/${id}/analysis`),

  reviewInvoice: (
    id: number | string,
    data: Partial<InvoiceReview>,
  ) =>
    request<{
      invoice_id: number
      verification_status: string
      message: string
    }>(`/api/invoices/${id}/review`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  confirmInvoice: (id: number | string) =>
    request<{
      invoice_id: number
      verification_status: string
      message: string
    }>(`/api/invoices/${id}/confirm`, {
      method: 'POST',
    }),

  deleteInvoice: (id: number | string) =>
    request<{ message: string }>(`/api/invoices/${id}`, {
      method: 'DELETE',
    }),

  getInvoiceSummary: (
    startDate: string,
    endDate: string,
    businessId = 1,
  ) =>
    request<{
      business_id: number
      start_date: string
      end_date: string
      invoice_count: number
      total_amount: string
      currency: string
      business_name: string
    }>(
      `/api/ai-data/summary?business_id=${businessId}&start_date=${startDate}&end_date=${endDate}`,
    ),

    
  getInvoiceSummaryAll: (businessId = 1) =>
    request<{
        business_id: number
        start_date: string | null
        end_date: string | null
        invoice_count: number
        total_amount: string
        currency: string
        business_name: string
    }>(`/api/ai-data/summary?business_id=${businessId}`),

}
