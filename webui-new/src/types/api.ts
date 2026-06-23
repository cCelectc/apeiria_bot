export interface ApiResponse<T> {
  data: T
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface ApiError {
  code: string
  message: string
  details?: Record<string, string[]>
}

export interface PaginationParams {
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: "asc" | "desc"
}
