import { describe, expect, it } from "vitest";

import type {
	ApiListResponse,
	ApiResponse,
	ErrorDetail,
	ErrorResponse,
	PaginationMeta,
} from "./api";

describe("API Response Types", () => {
	describe("ApiResponse", () => {
		it("wraps a single resource in data envelope", () => {
			const response: ApiResponse<{ id: string; name: string }> = {
				data: { id: "abc-123", name: "Test" },
			};

			expect(response.data.id).toBe("abc-123");
			expect(response.data.name).toBe("Test");
		});

		it("accepts any data type", () => {
			const stringResponse: ApiResponse<string> = { data: "hello" };
			const numberResponse: ApiResponse<number> = { data: 42 };

			expect(stringResponse.data).toBe("hello");
			expect(numberResponse.data).toBe(42);
		});
	});

	describe("PaginationMeta", () => {
		it("contains all pagination fields", () => {
			const meta: PaginationMeta = {
				total: 100,
				page: 1,
				per_page: 20,
				total_pages: 5,
			};

			expect(meta.total).toBe(100);
			expect(meta.page).toBe(1);
			expect(meta.per_page).toBe(20);
			expect(meta.total_pages).toBe(5);
		});

		it("represents an empty collection", () => {
			const meta: PaginationMeta = {
				total: 0,
				page: 1,
				per_page: 20,
				total_pages: 0,
			};

			expect(meta.total).toBe(0);
			expect(meta.total_pages).toBe(0);
		});
	});

	describe("ApiListResponse", () => {
		it("wraps a collection with pagination meta", () => {
			const response: ApiListResponse<{ id: string }> = {
				data: [{ id: "1" }, { id: "2" }],
				meta: { total: 25, page: 1, per_page: 20, total_pages: 2 },
			};

			expect(response.data).toHaveLength(2);
			expect(response.meta.total).toBe(25);
			expect(response.meta.total_pages).toBe(2);
		});

		it("represents an empty collection", () => {
			const response: ApiListResponse<string> = {
				data: [],
				meta: { total: 0, page: 1, per_page: 20, total_pages: 0 },
			};

			expect(response.data).toHaveLength(0);
			expect(response.meta.total).toBe(0);
		});
	});

	describe("ErrorDetail", () => {
		it("contains code and message", () => {
			const detail: ErrorDetail = {
				code: "NOT_FOUND",
				message: "Resource not found",
			};

			expect(detail.code).toBe("NOT_FOUND");
			expect(detail.message).toBe("Resource not found");
			expect(detail.details).toBeUndefined();
		});

		it("optionally includes field-level details", () => {
			const detail: ErrorDetail = {
				code: "VALIDATION_ERROR",
				message: "Invalid request",
				details: [
					{ field: "email", message: "Invalid email format" },
					{ field: "name", message: "Name is required" },
				],
			};

			expect(detail.details).toHaveLength(2);
			expect(detail.details?.[0]).toEqual({
				field: "email",
				message: "Invalid email format",
			});
		});
	});

	describe("ErrorResponse", () => {
		it("wraps ErrorDetail in error envelope", () => {
			const response: ErrorResponse = {
				error: {
					code: "INTERNAL_ERROR",
					message: "Something went wrong",
				},
			};

			expect(response.error.code).toBe("INTERNAL_ERROR");
			expect(response.error.message).toBe("Something went wrong");
		});
	});
});
