/**
 * API response envelope types matching backend/app/core/responses.py.
 *
 * REQ-006 §7.2: Consistent response format for all API endpoints.
 * REQ-012 §4.3: Typed API client with response envelope parsing.
 */

/**
 * Pagination metadata included in all list responses.
 *
 * Matches backend PaginationMeta (REQ-006 §7.3).
 * - page is 1-indexed
 * - total_pages is computed server-side
 */
export interface PaginationMeta {
	total: number;
	page: number;
	per_page: number;
	total_pages: number;
}

/**
 * Standard response envelope for a single resource.
 * Backend: DataResponse[T]
 *
 * All single-resource endpoints return: `{ "data": T }`.
 */
export interface ApiResponse<T> {
	data: T;
}

/**
 * Standard response envelope for collections with pagination.
 * Backend: ListResponse[T]
 *
 * All list endpoints return: `{ "data": T[], "meta": PaginationMeta }`.
 */
export interface ApiListResponse<T> {
	data: T[];
	meta: PaginationMeta;
}

/**
 * Error detail within the error response envelope.
 *
 * Matches backend ErrorDetail (REQ-006 §8.2).
 * - code: Machine-readable error code (e.g., "NOT_FOUND")
 * - message: Human-readable error message
 * - details: Optional field-level validation errors
 */
export interface ErrorDetail {
	code: string;
	message: string;
	details?: Record<string, unknown>[];
}

/**
 * Standard error response envelope.
 *
 * All error responses return: `{ "error": ErrorDetail }`.
 */
export interface ErrorResponse {
	error: ErrorDetail;
}
