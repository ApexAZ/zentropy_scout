/**
 * Typed API client with fetch wrapper and response envelope parsing.
 *
 * REQ-012 §4.3: All REST calls wrapped with consistent error handling.
 * REQ-006: Response envelope format (ApiResponse, ApiListResponse, ErrorResponse).
 *
 * Features:
 * - Base URL from NEXT_PUBLIC_API_URL environment variable
 * - JSON serialization/deserialization
 * - Typed error responses (ApiError class)
 * - 429 retry with exponential backoff (max 3 retries)
 * - AbortSignal support for request cancellation
 */

import type { ErrorResponse } from "../types/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_BASE_URL = "http://localhost:8000/api/v1";
const MAX_RETRIES = 3;
const INITIAL_BACKOFF_MS = 1000;
const MAX_RETRY_AFTER_SECONDS = 30;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Options for API requests. */
export interface RequestOptions {
	method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
	body?: unknown;
	params?: Record<string, string | number | boolean | undefined | null>;
	signal?: AbortSignal;
	headers?: Record<string, string>;
}

// ---------------------------------------------------------------------------
// ApiError
// ---------------------------------------------------------------------------

/**
 * Structured error thrown by the API client.
 *
 * - code: Machine-readable error code (e.g., "NOT_FOUND", "VALIDATION_ERROR")
 * - status: HTTP status code (0 for network errors)
 * - details: Optional field-level validation errors
 */
export class ApiError extends Error {
	readonly code: string;
	readonly status: number;
	readonly details?: Record<string, unknown>[];

	constructor(
		code: string,
		message: string,
		status: number,
		details?: Record<string, unknown>[],
	) {
		super(message);
		this.name = "ApiError";
		this.code = code;
		this.status = status;
		this.details = details;
	}
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function getBaseUrl(): string {
	// Use || (not ??) intentionally: empty string should also fall back to default
	return process.env.NEXT_PUBLIC_API_URL || DEFAULT_BASE_URL;
}

async function sleep(ms: number): Promise<void> {
	return new Promise((resolve) => setTimeout(resolve, ms));
}

function calculateBackoff(
	attempt: number,
	retryAfterHeader: string | null,
): number {
	if (retryAfterHeader) {
		const seconds = Number.parseInt(retryAfterHeader, 10);
		if (!Number.isNaN(seconds) && seconds > 0) {
			return Math.min(seconds, MAX_RETRY_AFTER_SECONDS) * 1000;
		}
	}
	return INITIAL_BACKOFF_MS * 2 ** (attempt - 1);
}

async function parseErrorResponse(response: Response): Promise<ApiError> {
	try {
		const body = (await response.json()) as ErrorResponse;
		return new ApiError(
			body.error.code,
			body.error.message,
			response.status,
			body.error.details,
		);
	} catch {
		return new ApiError(
			"UNKNOWN_ERROR",
			`Request failed with status ${response.status}`,
			response.status,
		);
	}
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Build a full URL from a path and optional query params.
 *
 * Prepends the base URL from NEXT_PUBLIC_API_URL (or fallback) and appends
 * query parameters. Undefined/null param values are omitted.
 */
export function buildUrl(
	path: string,
	params?: Record<string, string | number | boolean | undefined | null>,
): string {
	const base = getBaseUrl().replace(/\/+$/, "");
	const normalizedPath = path.startsWith("/") ? path : `/${path}`;
	const url = new URL(`${base}${normalizedPath}`);

	if (params) {
		for (const [key, value] of Object.entries(params)) {
			if (value !== undefined && value !== null) {
				url.searchParams.set(key, String(value));
			}
		}
	}

	return url.toString();
}

/**
 * Core typed fetch wrapper with error handling and 429 retry.
 *
 * - Parses JSON response body and returns as type T
 * - Returns undefined for 204 No Content responses
 * - Throws ApiError for non-OK responses (with parsed error body)
 * - Retries 429 responses with exponential backoff (max 3 retries)
 * - Respects Retry-After header when present
 */
export async function apiFetch<T>(
	path: string,
	options?: RequestOptions,
): Promise<T> {
	const url = buildUrl(path, options?.params);
	const method = options?.method ?? "GET";

	const headers: Record<string, string> = { ...options?.headers };
	if (options?.body !== undefined) {
		headers["Content-Type"] = "application/json";
	}

	const fetchOptions: RequestInit = {
		method,
		headers,
		signal: options?.signal,
		...(options?.body !== undefined && {
			body: JSON.stringify(options.body),
		}),
	};

	let lastRetryAfter: string | null = null;

	for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
		if (attempt > 0) {
			await sleep(calculateBackoff(attempt, lastRetryAfter));
		}

		let response: Response;
		try {
			response = await fetch(url, fetchOptions);
		} catch {
			throw new ApiError("NETWORK_ERROR", "Unable to connect to the server", 0);
		}

		if (response.status === 429) {
			lastRetryAfter = response.headers.get("Retry-After");
			if (attempt === MAX_RETRIES) {
				throw new ApiError("RATE_LIMITED", "Too many requests", 429);
			}
			continue;
		}

		if (!response.ok) {
			throw await parseErrorResponse(response);
		}

		if (response.status === 204) {
			return undefined as T;
		}

		return (await response.json()) as T;
	}

	// Unreachable — loop always returns or throws
	throw new ApiError("RATE_LIMITED", "Too many requests", 429);
}

/** GET request with optional query params. */
export async function apiGet<T>(
	path: string,
	params?: Record<string, string | number | boolean | undefined | null>,
): Promise<T> {
	return apiFetch<T>(path, { params });
}

/** POST request with JSON body. */
export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
	return apiFetch<T>(path, { method: "POST", body });
}

/** PATCH request with JSON body. */
export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
	return apiFetch<T>(path, { method: "PATCH", body });
}

/** PUT request with JSON body. */
export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
	return apiFetch<T>(path, { method: "PUT", body });
}

/** DELETE request. Returns void (expects 204 No Content). */
export async function apiDelete(path: string): Promise<void> {
	return apiFetch<void>(path, { method: "DELETE" });
}
