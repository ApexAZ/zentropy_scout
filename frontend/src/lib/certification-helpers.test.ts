/**
 * Tests for shared certification helper functions.
 *
 * REQ-012 §7.2.3: Verify conversion between API Certification entities,
 * form values, and request bodies.
 */

import { describe, expect, it } from "vitest";

import type { Certification } from "@/types/persona";

import { toFormValues, toRequestBody } from "./certification-helpers";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const MOCK_ENTRY: Certification = {
	id: "cert-001",
	persona_id: "p-001",
	certification_name: "AWS Solutions Architect",
	issuing_organization: "Amazon Web Services",
	date_obtained: "2023-06-15",
	expiration_date: "2026-06-15",
	credential_id: "ABC-123",
	verification_url: "https://verify.example.com/abc",
	display_order: 0,
};

// ---------------------------------------------------------------------------
// toFormValues
// ---------------------------------------------------------------------------

describe("toFormValues", () => {
	it("converts a full Certification entry to form values", () => {
		const result = toFormValues(MOCK_ENTRY);

		expect(result).toEqual({
			certification_name: "AWS Solutions Architect",
			issuing_organization: "Amazon Web Services",
			date_obtained: "2023-06-15",
			does_not_expire: false,
			expiration_date: "2026-06-15",
			credential_id: "ABC-123",
			verification_url: "https://verify.example.com/abc",
		});
	});

	it("sets does_not_expire when expiration_date is null", () => {
		const entryNoExpiry: Certification = {
			...MOCK_ENTRY,
			expiration_date: null,
		};

		const result = toFormValues(entryNoExpiry);

		expect(result.does_not_expire).toBe(true);
		expect(result.expiration_date).toBe("");
	});

	it("converts null optional fields to empty strings", () => {
		const entryWithNulls: Certification = {
			...MOCK_ENTRY,
			credential_id: null,
			verification_url: null,
		};

		const result = toFormValues(entryWithNulls);

		expect(result.credential_id).toBe("");
		expect(result.verification_url).toBe("");
	});
});

// ---------------------------------------------------------------------------
// toRequestBody
// ---------------------------------------------------------------------------

describe("toRequestBody", () => {
	it("converts form data to request body", () => {
		const result = toRequestBody({
			certification_name: "PMP",
			issuing_organization: "PMI",
			date_obtained: "2024-01-15",
			does_not_expire: false,
			expiration_date: "2027-01-15",
			credential_id: "PMP-999",
			verification_url: "https://pmi.org/verify/999",
		});

		expect(result).toEqual({
			certification_name: "PMP",
			issuing_organization: "PMI",
			date_obtained: "2024-01-15",
			expiration_date: "2027-01-15",
			credential_id: "PMP-999",
			verification_url: "https://pmi.org/verify/999",
		});
	});

	it("sets expiration_date to null when does_not_expire is true", () => {
		const result = toRequestBody({
			certification_name: "PMP",
			issuing_organization: "PMI",
			date_obtained: "2024-01-15",
			does_not_expire: true,
			expiration_date: "",
			credential_id: "",
			verification_url: "",
		});

		expect(result.expiration_date).toBeNull();
	});

	it("converts empty optional strings to null", () => {
		const result = toRequestBody({
			certification_name: "PMP",
			issuing_organization: "PMI",
			date_obtained: "2024-01-15",
			does_not_expire: false,
			expiration_date: "",
			credential_id: "",
			verification_url: "",
		});

		expect(result.expiration_date).toBeNull();
		expect(result.credential_id).toBeNull();
		expect(result.verification_url).toBeNull();
	});
});
