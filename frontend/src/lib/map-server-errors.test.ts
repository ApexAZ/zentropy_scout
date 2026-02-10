/**
 * Tests for mapServerErrors utility.
 *
 * REQ-012 §13.2: Server errors mapped to fields.
 */

import { describe, expect, it, vi } from "vitest";

import { mapServerErrors } from "./map-server-errors";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SERVER_ERROR_TYPE = "server";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("mapServerErrors", () => {
	it("maps field errors to setError calls", () => {
		const setError = vi.fn();
		const fieldErrors = [
			{ field: "email", message: "Email already exists" },
			{ field: "name", message: "Name is too long" },
		];

		mapServerErrors(fieldErrors, setError);

		expect(setError).toHaveBeenCalledTimes(2);
		expect(setError).toHaveBeenCalledWith("email", {
			type: SERVER_ERROR_TYPE,
			message: "Email already exists",
		});
		expect(setError).toHaveBeenCalledWith("name", {
			type: SERVER_ERROR_TYPE,
			message: "Name is too long",
		});
	});

	it("maps nested field paths", () => {
		const setError = vi.fn();
		const fieldErrors = [
			{ field: "address.city", message: "City is required" },
		];

		mapServerErrors(fieldErrors, setError);

		expect(setError).toHaveBeenCalledWith("address.city", {
			type: SERVER_ERROR_TYPE,
			message: "City is required",
		});
	});

	it("handles empty field errors array", () => {
		const setError = vi.fn();

		mapServerErrors([], setError);

		expect(setError).not.toHaveBeenCalled();
	});

	it("skips dangerous field names to prevent prototype pollution", () => {
		const setError = vi.fn();
		const fieldErrors = [
			{ field: "__proto__", message: "Malicious" },
			{ field: "constructor", message: "Malicious" },
			{ field: "prototype", message: "Malicious" },
			{ field: "name", message: "Valid error" },
		];

		mapServerErrors(fieldErrors, setError);

		expect(setError).toHaveBeenCalledTimes(1);
		expect(setError).toHaveBeenCalledWith("name", {
			type: SERVER_ERROR_TYPE,
			message: "Valid error",
		});
	});

	it("maps root-level error when field is 'root'", () => {
		const setError = vi.fn();
		const fieldErrors = [{ field: "root", message: "Something went wrong" }];

		mapServerErrors(fieldErrors, setError);

		expect(setError).toHaveBeenCalledWith("root", {
			type: SERVER_ERROR_TYPE,
			message: "Something went wrong",
		});
	});
});
