/**
 * Tests for the typed API client.
 *
 * REQ-012 §4.3: API client with typed fetch wrapper, error handling,
 * response envelope parsing, and 429 retry with exponential backoff.
 * REQ-013 §8.8: credentials: 'include' on all fetch calls, 401 interceptor.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiListResponse, ApiResponse } from "../types/api";

import {
	ApiError,
	apiDelete,
	apiFetch,
	apiGet,
	apiPatch,
	apiPost,
	apiPut,
	apiUploadFile,
	buildUrl,
} from "./api-client";
import { createQueryClient, setActiveQueryClient } from "./query-client";

// ---------------------------------------------------------------------------
// Test constants
// ---------------------------------------------------------------------------

const BASE_URL = "http://localhost:8000/api/v1";
const PERSONAS_PATH = "/personas";
const PERSONA_PATH = "/personas/abc";
const TEST_PATH = "/test";
const JSON_CONTENT_TYPE = "application/json";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function mockJsonResponse(body: unknown, init?: ResponseInit): Response {
	return new Response(JSON.stringify(body), {
		status: 200,
		headers: { "Content-Type": JSON_CONTENT_TYPE },
		...init,
	});
}

function mockErrorResponse(
	code: string,
	message: string,
	status: number,
	details?: Record<string, unknown>[],
): Response {
	return new Response(JSON.stringify({ error: { code, message, details } }), {
		status,
		headers: { "Content-Type": JSON_CONTENT_TYPE },
	});
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("API Client", () => {
	let fetchMock: ReturnType<typeof vi.fn>;

	beforeEach(() => {
		vi.stubEnv("NEXT_PUBLIC_API_URL", BASE_URL);
		fetchMock = vi.fn();
		vi.stubGlobal("fetch", fetchMock);
	});

	afterEach(() => {
		vi.unstubAllEnvs();
		vi.restoreAllMocks();
		vi.useRealTimers();
	});

	// -----------------------------------------------------------------------
	// ApiError
	// -----------------------------------------------------------------------

	describe("ApiError", () => {
		it("stores code, message, and status", () => {
			const error = new ApiError("NOT_FOUND", "Resource not found", 404);

			expect(error.code).toBe("NOT_FOUND");
			expect(error.message).toBe("Resource not found");
			expect(error.status).toBe(404);
		});

		it("stores optional details array", () => {
			const details = [{ field: "name", message: "Required" }];
			const error = new ApiError("VALIDATION_ERROR", "Invalid", 400, details);

			expect(error.details).toEqual(details);
		});

		it("extends Error with name ApiError", () => {
			const error = new ApiError("TEST", "test error", 400);

			expect(error).toBeInstanceOf(Error);
			expect(error.name).toBe("ApiError");
		});

		it("has undefined details when not provided", () => {
			const error = new ApiError("TEST", "test", 500);

			expect(error.details).toBeUndefined();
		});
	});

	// -----------------------------------------------------------------------
	// buildUrl
	// -----------------------------------------------------------------------

	describe("buildUrl", () => {
		it("prepends base URL to path", () => {
			const url = buildUrl("/personas/123");

			expect(url).toBe(`${BASE_URL}/personas/123`);
		});

		it("appends query params as search params", () => {
			const url = buildUrl("/job-postings", { page: 1, per_page: 20 });
			const parsed = new URL(url);

			expect(parsed.searchParams.get("page")).toBe("1");
			expect(parsed.searchParams.get("per_page")).toBe("20");
		});

		it("omits undefined and null params", () => {
			const url = buildUrl("/jobs", {
				status: "active",
				sort: undefined,
				filter: null,
			});
			const parsed = new URL(url);

			expect(parsed.searchParams.get("status")).toBe("active");
			expect(parsed.searchParams.has("sort")).toBe(false);
			expect(parsed.searchParams.has("filter")).toBe(false);
		});

		it("handles path without leading slash", () => {
			const url = buildUrl("personas/123");

			expect(url).toBe(`${BASE_URL}/personas/123`);
		});

		it("handles empty params object", () => {
			const url = buildUrl(PERSONAS_PATH, {});

			expect(url).toBe(`${BASE_URL}${PERSONAS_PATH}`);
		});

		it("encodes param values correctly", () => {
			const url = buildUrl("/jobs", { company_name: "Foo & Bar" });
			const parsed = new URL(url);

			expect(parsed.searchParams.get("company_name")).toBe("Foo & Bar");
		});

		it("uses fallback base URL when env var is empty", () => {
			vi.stubEnv("NEXT_PUBLIC_API_URL", "");
			const url = buildUrl(PERSONAS_PATH);

			expect(url).toBe(`http://localhost:8000/api/v1${PERSONAS_PATH}`);
		});
	});

	// -----------------------------------------------------------------------
	// apiFetch — successful requests
	// -----------------------------------------------------------------------

	describe("apiFetch — successful requests", () => {
		it("makes GET request and returns parsed JSON", async () => {
			const body: ApiResponse<{ id: string }> = { data: { id: "abc" } };
			fetchMock.mockResolvedValueOnce(mockJsonResponse(body));

			const result = await apiFetch<ApiResponse<{ id: string }>>(PERSONA_PATH);

			expect(result.data.id).toBe("abc");
			expect(fetchMock).toHaveBeenCalledWith(
				`${BASE_URL}${PERSONA_PATH}`,
				expect.objectContaining({ method: "GET" }),
			);
		});

		it("makes POST request with JSON body", async () => {
			const body: ApiResponse<{ id: string }> = {
				data: { id: "new-id" },
			};
			fetchMock.mockResolvedValueOnce(mockJsonResponse(body, { status: 201 }));

			const result = await apiFetch<ApiResponse<{ id: string }>>(
				PERSONAS_PATH,
				{ method: "POST", body: { name: "Test Persona" } },
			);

			expect(result.data.id).toBe("new-id");
			expect(fetchMock).toHaveBeenCalledWith(
				`${BASE_URL}${PERSONAS_PATH}`,
				expect.objectContaining({
					method: "POST",
					body: JSON.stringify({ name: "Test Persona" }),
				}),
			);
		});

		it("makes PATCH request with JSON body", async () => {
			fetchMock.mockResolvedValueOnce(
				mockJsonResponse({ data: { name: "Updated" } }),
			);

			await apiFetch(PERSONA_PATH, {
				method: "PATCH",
				body: { name: "Updated" },
			});

			expect(fetchMock).toHaveBeenCalledWith(
				`${BASE_URL}${PERSONA_PATH}`,
				expect.objectContaining({
					method: "PATCH",
					body: JSON.stringify({ name: "Updated" }),
				}),
			);
		});

		it("makes DELETE request and returns void for 204", async () => {
			fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

			const result = await apiFetch<void>(PERSONA_PATH, {
				method: "DELETE",
			});

			expect(result).toBeUndefined();
			expect(fetchMock).toHaveBeenCalledWith(
				`${BASE_URL}${PERSONA_PATH}`,
				expect.objectContaining({ method: "DELETE" }),
			);
		});

		it("sets Content-Type: application/json for requests with body", async () => {
			fetchMock.mockResolvedValueOnce(mockJsonResponse({ data: {} }));

			await apiFetch(PERSONAS_PATH, {
				method: "POST",
				body: { name: "Test" },
			});

			expect(fetchMock).toHaveBeenCalledWith(
				expect.any(String),
				expect.objectContaining({
					headers: expect.objectContaining({
						"Content-Type": JSON_CONTENT_TYPE,
					}),
				}),
			);
		});

		it("does not set Content-Type for requests without body", async () => {
			fetchMock.mockResolvedValueOnce(mockJsonResponse({ data: {} }));

			await apiFetch(PERSONA_PATH);

			const callHeaders = fetchMock.mock.calls[0][1]?.headers ?? {};
			expect(callHeaders).not.toHaveProperty("Content-Type");
		});

		it("passes AbortSignal through to fetch", async () => {
			fetchMock.mockResolvedValueOnce(mockJsonResponse({ data: {} }));
			const controller = new AbortController();

			await apiFetch(PERSONA_PATH, { signal: controller.signal });

			expect(fetchMock).toHaveBeenCalledWith(
				expect.any(String),
				expect.objectContaining({ signal: controller.signal }),
			);
		});

		it("returns list response with pagination meta", async () => {
			const body: ApiListResponse<{ id: string }> = {
				data: [{ id: "1" }, { id: "2" }],
				meta: { total: 42, page: 1, per_page: 20, total_pages: 3 },
			};
			fetchMock.mockResolvedValueOnce(mockJsonResponse(body));

			const result = await apiFetch<ApiListResponse<{ id: string }>>(
				"/job-postings",
				{ params: { page: 1, per_page: 20 } },
			);

			expect(result.data).toHaveLength(2);
			expect(result.meta.total).toBe(42);
			expect(result.meta.total_pages).toBe(3);
		});
	});

	// -----------------------------------------------------------------------
	// apiFetch — error handling
	// -----------------------------------------------------------------------

	describe("apiFetch — error handling", () => {
		it("throws ApiError on 400 with validation details", async () => {
			const details = [{ field: "name", message: "Required" }];
			fetchMock.mockResolvedValueOnce(
				mockErrorResponse("VALIDATION_ERROR", "Invalid input", 400, details),
			);

			const error = await apiFetch(PERSONAS_PATH, {
				method: "POST",
				body: {},
			}).catch((e: unknown) => e);

			expect(error).toBeInstanceOf(ApiError);
			expect((error as ApiError).code).toBe("VALIDATION_ERROR");
			expect((error as ApiError).message).toBe("Invalid input");
			expect((error as ApiError).status).toBe(400);
			expect((error as ApiError).details).toEqual(details);
		});

		it("throws ApiError on 404 response", async () => {
			fetchMock.mockResolvedValueOnce(
				mockErrorResponse("NOT_FOUND", "Persona not found", 404),
			);

			const error = await apiFetch("/personas/missing").catch(
				(e: unknown) => e,
			);

			expect(error).toBeInstanceOf(ApiError);
			expect((error as ApiError).code).toBe("NOT_FOUND");
			expect((error as ApiError).status).toBe(404);
		});

		it("throws ApiError on 500 response", async () => {
			fetchMock.mockResolvedValueOnce(
				mockErrorResponse("INTERNAL_ERROR", "Server error", 500),
			);

			const error = await apiFetch(PERSONAS_PATH).catch((e: unknown) => e);

			expect(error).toBeInstanceOf(ApiError);
			expect((error as ApiError).code).toBe("INTERNAL_ERROR");
			expect((error as ApiError).status).toBe(500);
		});

		it("throws ApiError with UNKNOWN_ERROR when body is not parseable", async () => {
			fetchMock.mockResolvedValueOnce(
				new Response("Not JSON", { status: 500 }),
			);

			const error = await apiFetch(PERSONAS_PATH).catch((e: unknown) => e);

			expect(error).toBeInstanceOf(ApiError);
			expect((error as ApiError).code).toBe("UNKNOWN_ERROR");
			expect((error as ApiError).status).toBe(500);
		});

		it("throws ApiError with NETWORK_ERROR on fetch failure", async () => {
			fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

			const error = await apiFetch(PERSONAS_PATH).catch((e: unknown) => e);

			expect(error).toBeInstanceOf(ApiError);
			expect((error as ApiError).code).toBe("NETWORK_ERROR");
			expect((error as ApiError).message).toBe(
				"Unable to connect to the server",
			);
			expect((error as ApiError).status).toBe(0);
		});
	});

	// -----------------------------------------------------------------------
	// apiFetch — 429 retry with exponential backoff
	// -----------------------------------------------------------------------

	describe("apiFetch — 429 retry", () => {
		it("retries on 429 and succeeds on next attempt", async () => {
			vi.useFakeTimers();
			fetchMock
				.mockResolvedValueOnce(new Response(null, { status: 429 }))
				.mockResolvedValueOnce(mockJsonResponse({ data: "recovered" }));

			const promise = apiFetch<ApiResponse<string>>(TEST_PATH);
			await vi.runAllTimersAsync();
			const result = await promise;

			expect(result.data).toBe("recovered");
			expect(fetchMock).toHaveBeenCalledTimes(2);
		});

		it("retries up to 3 times before succeeding", async () => {
			vi.useFakeTimers();
			fetchMock
				.mockResolvedValueOnce(new Response(null, { status: 429 }))
				.mockResolvedValueOnce(new Response(null, { status: 429 }))
				.mockResolvedValueOnce(new Response(null, { status: 429 }))
				.mockResolvedValueOnce(mockJsonResponse({ data: "recovered" }));

			const promise = apiFetch<ApiResponse<string>>(TEST_PATH);
			await vi.runAllTimersAsync();
			const result = await promise;

			expect(result.data).toBe("recovered");
			expect(fetchMock).toHaveBeenCalledTimes(4);
		});

		it("throws RATE_LIMITED after exhausting max retries", async () => {
			vi.useFakeTimers();
			fetchMock.mockResolvedValue(new Response(null, { status: 429 }));

			const promise = apiFetch(TEST_PATH).catch((e: unknown) => e);
			await vi.runAllTimersAsync();
			const error = await promise;

			expect(error).toBeInstanceOf(ApiError);
			expect((error as ApiError).code).toBe("RATE_LIMITED");
			expect((error as ApiError).status).toBe(429);
			expect(fetchMock).toHaveBeenCalledTimes(4);
		});

		it("respects Retry-After header value in seconds", async () => {
			vi.useFakeTimers();
			fetchMock
				.mockResolvedValueOnce(
					new Response(null, {
						status: 429,
						headers: { "Retry-After": "5" },
					}),
				)
				.mockResolvedValueOnce(mockJsonResponse({ data: "recovered" }));

			const promise = apiFetch<ApiResponse<string>>(TEST_PATH);

			// Should not have retried yet before 5 seconds
			await vi.advanceTimersByTimeAsync(4999);
			expect(fetchMock).toHaveBeenCalledTimes(1);

			// After 5 seconds, retry fires
			await vi.advanceTimersByTimeAsync(1);
			const result = await promise;

			expect(fetchMock).toHaveBeenCalledTimes(2);
			expect(result.data).toBe("recovered");
		});

		it("clamps Retry-After to maximum of 30 seconds", async () => {
			vi.useFakeTimers();
			fetchMock
				.mockResolvedValueOnce(
					new Response(null, {
						status: 429,
						headers: { "Retry-After": "999999" },
					}),
				)
				.mockResolvedValueOnce(mockJsonResponse({ data: "recovered" }));

			const promise = apiFetch<ApiResponse<string>>(TEST_PATH);

			// Should not retry before 30 seconds (clamped from 999999)
			await vi.advanceTimersByTimeAsync(29999);
			expect(fetchMock).toHaveBeenCalledTimes(1);

			// After 30 seconds, retry fires
			await vi.advanceTimersByTimeAsync(1);
			const result = await promise;

			expect(fetchMock).toHaveBeenCalledTimes(2);
			expect(result.data).toBe("recovered");
		});

		it("does not retry non-429 error responses", async () => {
			fetchMock.mockResolvedValueOnce(
				mockErrorResponse("NOT_FOUND", "Not found", 404),
			);

			await expect(apiFetch("/missing")).rejects.toThrow(ApiError);
			expect(fetchMock).toHaveBeenCalledTimes(1);
		});
	});

	// -----------------------------------------------------------------------
	// Convenience methods
	// -----------------------------------------------------------------------

	describe("convenience methods", () => {
		it("apiGet makes GET request with params", async () => {
			fetchMock.mockResolvedValueOnce(
				mockJsonResponse({
					data: [],
					meta: { total: 0, page: 1, per_page: 20, total_pages: 0 },
				}),
			);

			await apiGet("/job-postings", { status: "active", page: 1 });

			const calledUrl = fetchMock.mock.calls[0][0] as string;
			const parsed = new URL(calledUrl);
			expect(parsed.searchParams.get("status")).toBe("active");
			expect(parsed.searchParams.get("page")).toBe("1");
			expect(fetchMock.mock.calls[0][1].method).toBe("GET");
		});

		it("apiPost makes POST request with body", async () => {
			fetchMock.mockResolvedValueOnce(
				mockJsonResponse({ data: { id: "new" } }, { status: 201 }),
			);

			await apiPost(PERSONAS_PATH, { name: "Test" });

			expect(fetchMock).toHaveBeenCalledWith(
				expect.any(String),
				expect.objectContaining({
					method: "POST",
					body: JSON.stringify({ name: "Test" }),
				}),
			);
		});

		it("apiPatch makes PATCH request with body", async () => {
			fetchMock.mockResolvedValueOnce(
				mockJsonResponse({ data: { name: "Updated" } }),
			);

			await apiPatch(PERSONA_PATH, { name: "Updated" });

			expect(fetchMock).toHaveBeenCalledWith(
				expect.any(String),
				expect.objectContaining({
					method: "PATCH",
					body: JSON.stringify({ name: "Updated" }),
				}),
			);
		});

		it("apiPut makes PUT request with body", async () => {
			fetchMock.mockResolvedValueOnce(
				mockJsonResponse({ data: { name: "Replaced" } }),
			);

			await apiPut(PERSONA_PATH, { name: "Replaced" });

			expect(fetchMock).toHaveBeenCalledWith(
				expect.any(String),
				expect.objectContaining({
					method: "PUT",
					body: JSON.stringify({ name: "Replaced" }),
				}),
			);
		});

		it("apiDelete makes DELETE request", async () => {
			fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

			await apiDelete(PERSONA_PATH);

			expect(fetchMock).toHaveBeenCalledWith(
				expect.stringContaining(PERSONA_PATH),
				expect.objectContaining({ method: "DELETE" }),
			);
		});
	});

	// -----------------------------------------------------------------------
	// apiUploadFile
	// -----------------------------------------------------------------------

	describe("apiUploadFile", () => {
		const RESUME_FILES_PATH = "/resume-files";
		const PDF_MIME_TYPE = "application/pdf";
		const TEST_FILENAME = "resume.pdf";

		function makePdfFile(name = TEST_FILENAME): File {
			return new File(["content"], name, { type: PDF_MIME_TYPE });
		}

		it("sends FormData with file via POST", async () => {
			fetchMock.mockResolvedValueOnce(
				mockJsonResponse({ data: { id: "file-1" } }, { status: 201 }),
			);

			await apiUploadFile(RESUME_FILES_PATH, makePdfFile());

			expect(fetchMock).toHaveBeenCalledTimes(1);
			const [calledUrl, calledOptions] = fetchMock.mock.calls[0] as [
				string,
				RequestInit,
			];
			expect(calledUrl).toBe(`${BASE_URL}${RESUME_FILES_PATH}`);
			expect(calledOptions.method).toBe("POST");
			expect(calledOptions.body).toBeInstanceOf(FormData);
		});

		it("does not set Content-Type header (browser auto-sets boundary)", async () => {
			fetchMock.mockResolvedValueOnce(
				mockJsonResponse({ data: {} }, { status: 201 }),
			);

			await apiUploadFile(RESUME_FILES_PATH, makePdfFile());

			const calledOptions = fetchMock.mock.calls[0][1] as RequestInit;
			const headers = calledOptions.headers as
				| Record<string, string>
				| undefined;
			expect(headers).toBeUndefined();
		});

		it("includes additional form fields in FormData", async () => {
			fetchMock.mockResolvedValueOnce(
				mockJsonResponse({ data: {} }, { status: 201 }),
			);

			await apiUploadFile(RESUME_FILES_PATH, makePdfFile(), {
				persona_id: "p-123",
			});

			const formData = (fetchMock.mock.calls[0][1] as RequestInit)
				.body as FormData;
			expect(formData.get("file")).toBeInstanceOf(File);
			expect(formData.get("persona_id")).toBe("p-123");
		});

		it("returns parsed JSON response", async () => {
			const body = {
				data: { id: "file-1", file_name: TEST_FILENAME },
			};
			fetchMock.mockResolvedValueOnce(mockJsonResponse(body, { status: 201 }));

			const result = await apiUploadFile<typeof body>(
				RESUME_FILES_PATH,
				makePdfFile(),
			);

			expect(result.data.id).toBe("file-1");
			expect(result.data.file_name).toBe(TEST_FILENAME);
		});

		it("throws ApiError on error response", async () => {
			fetchMock.mockResolvedValueOnce(
				mockErrorResponse("VALIDATION_ERROR", "Invalid file type", 400),
			);
			const file = new File(["content"], "bad.txt", {
				type: "text/plain",
			});

			const error = await apiUploadFile(RESUME_FILES_PATH, file).catch(
				(e: unknown) => e,
			);

			expect(error).toBeInstanceOf(ApiError);
			expect((error as ApiError).code).toBe("VALIDATION_ERROR");
			expect((error as ApiError).status).toBe(400);
		});

		it("throws NETWORK_ERROR on fetch failure", async () => {
			fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

			const error = await apiUploadFile(RESUME_FILES_PATH, makePdfFile()).catch(
				(e: unknown) => e,
			);

			expect(error).toBeInstanceOf(ApiError);
			expect((error as ApiError).code).toBe("NETWORK_ERROR");
		});

		it("passes AbortSignal to fetch", async () => {
			fetchMock.mockResolvedValueOnce(
				mockJsonResponse({ data: {} }, { status: 201 }),
			);
			const controller = new AbortController();

			await apiUploadFile(RESUME_FILES_PATH, makePdfFile(), undefined, {
				signal: controller.signal,
			});

			expect(fetchMock).toHaveBeenCalledWith(
				expect.any(String),
				expect.objectContaining({ signal: controller.signal }),
			);
		});

		it("includes credentials: 'include' in fetch options", async () => {
			fetchMock.mockResolvedValueOnce(
				mockJsonResponse({ data: {} }, { status: 201 }),
			);

			await apiUploadFile(RESUME_FILES_PATH, makePdfFile());

			expect(fetchMock).toHaveBeenCalledWith(
				expect.any(String),
				expect.objectContaining({ credentials: "include" }),
			);
		});
	});

	// -----------------------------------------------------------------------
	// Credentials mode (REQ-013 §8.8)
	// -----------------------------------------------------------------------

	describe("credentials mode", () => {
		it("includes credentials: 'include' in apiFetch requests", async () => {
			fetchMock.mockResolvedValueOnce(mockJsonResponse({ data: {} }));

			await apiFetch(TEST_PATH);

			expect(fetchMock).toHaveBeenCalledWith(
				expect.any(String),
				expect.objectContaining({ credentials: "include" }),
			);
		});

		it("includes credentials: 'include' in POST requests with body", async () => {
			fetchMock.mockResolvedValueOnce(
				mockJsonResponse({ data: {} }, { status: 201 }),
			);

			await apiPost(PERSONAS_PATH, { name: "Test" });

			expect(fetchMock).toHaveBeenCalledWith(
				expect.any(String),
				expect.objectContaining({ credentials: "include" }),
			);
		});
	});

	// -----------------------------------------------------------------------
	// 401 interceptor (REQ-013 §8.8)
	// -----------------------------------------------------------------------

	describe("401 interceptor", () => {
		const TEST_ORIGIN = "http://localhost:3000";
		let originalLocation: Location;

		function mock401Response(): Response {
			return mockErrorResponse("UNAUTHORIZED", "Not authenticated", 401);
		}

		function mockWindowLocation(pathname: string): void {
			Object.defineProperty(window, "location", {
				value: {
					...originalLocation,
					href: `${TEST_ORIGIN}${pathname}`,
					pathname,
				},
				writable: true,
				configurable: true,
			});
		}

		beforeEach(() => {
			originalLocation = window.location;
			mockWindowLocation("/jobs");
		});

		afterEach(() => {
			Object.defineProperty(window, "location", {
				value: originalLocation,
				writable: true,
				configurable: true,
			});
			setActiveQueryClient(null);
		});

		it("redirects to /login on 401 response", async () => {
			fetchMock.mockResolvedValueOnce(mock401Response());

			await expect(apiFetch(PERSONAS_PATH)).rejects.toThrow(ApiError);

			expect(window.location.href).toBe("/login");
		});

		it("clears query cache on 401 response", async () => {
			const queryClient = createQueryClient();
			setActiveQueryClient(queryClient);
			const clearSpy = vi.spyOn(queryClient, "clear");

			fetchMock.mockResolvedValueOnce(mock401Response());

			await expect(apiFetch(PERSONAS_PATH)).rejects.toThrow(ApiError);

			expect(clearSpy).toHaveBeenCalled();
		});

		it("still throws ApiError with correct code after 401 redirect", async () => {
			fetchMock.mockResolvedValueOnce(mock401Response());

			const error = await apiFetch(PERSONAS_PATH).catch((e: unknown) => e);

			expect(error).toBeInstanceOf(ApiError);
			expect((error as ApiError).code).toBe("UNAUTHORIZED");
			expect((error as ApiError).status).toBe(401);
		});

		it("does not redirect when already on /login", async () => {
			mockWindowLocation("/login");
			fetchMock.mockResolvedValueOnce(mock401Response());

			await expect(apiFetch(PERSONAS_PATH)).rejects.toThrow(ApiError);

			expect(window.location.href).toBe(`${TEST_ORIGIN}/login`);
		});

		it("does not redirect when already on /register", async () => {
			mockWindowLocation("/register");
			fetchMock.mockResolvedValueOnce(mock401Response());

			await expect(apiFetch(PERSONAS_PATH)).rejects.toThrow(ApiError);

			expect(window.location.href).toBe(`${TEST_ORIGIN}/register`);
		});

		it("does not redirect on auth subpaths like /login-callback", async () => {
			mockWindowLocation("/login-callback");
			fetchMock.mockResolvedValueOnce(mock401Response());

			await expect(apiFetch(PERSONAS_PATH)).rejects.toThrow(ApiError);

			expect(window.location.href).toBe(`${TEST_ORIGIN}/login-callback`);
		});

		it("handles 401 in apiUploadFile", async () => {
			fetchMock.mockResolvedValueOnce(mock401Response());

			await expect(
				apiUploadFile(
					"/resume-files",
					new File(["x"], "test.pdf", { type: "application/pdf" }),
				),
			).rejects.toThrow(ApiError);

			expect(window.location.href).toBe("/login");
		});
	});
});
