/**
 * Tests for ingest type definitions.
 *
 * Validates const arrays, type structure, and compile-time contracts.
 */

import { describe, expect, it } from "vitest";

import type {
	ExtractedSkillPreview,
	IngestConfirmRequest,
	IngestJobPostingRequest,
	IngestJobPostingResponse,
	IngestPreview,
	IngestSourceName,
} from "./ingest";
import { INGEST_SOURCE_NAMES } from "./ingest";

// ---------------------------------------------------------------------------
// INGEST_SOURCE_NAMES
// ---------------------------------------------------------------------------

describe("INGEST_SOURCE_NAMES", () => {
	it("contains 8 source names", () => {
		expect(INGEST_SOURCE_NAMES).toHaveLength(8);
	});

	it("includes LinkedIn, Indeed, and Other", () => {
		expect(INGEST_SOURCE_NAMES).toContain("LinkedIn");
		expect(INGEST_SOURCE_NAMES).toContain("Indeed");
		expect(INGEST_SOURCE_NAMES).toContain("Other");
	});

	it("is a readonly tuple (as const)", () => {
		// as const creates a readonly tuple at the TS level; verify it's an array at runtime
		expect(Array.isArray(INGEST_SOURCE_NAMES)).toBe(true);
	});
});

// ---------------------------------------------------------------------------
// Type structure assertions (compile-time + runtime shape)
// ---------------------------------------------------------------------------

describe("IngestJobPostingRequest", () => {
	it("accepts a valid request shape", () => {
		const req: IngestJobPostingRequest = {
			raw_text: "Job posting text",
			source_name: "LinkedIn",
		};
		expect(req.raw_text).toBe("Job posting text");
		expect(req.source_url).toBeUndefined();
	});

	it("accepts optional source_url", () => {
		const req: IngestJobPostingRequest = {
			raw_text: "text",
			source_url: "https://example.com/job",
			source_name: "Indeed",
		};
		expect(req.source_url).toBe("https://example.com/job");
	});
});

describe("IngestJobPostingResponse", () => {
	it("has preview, confirmation_token, and expires_at", () => {
		const res: IngestJobPostingResponse = {
			preview: {
				job_title: "Engineer",
				company_name: "Acme",
				location: null,
				salary_min: null,
				salary_max: null,
				salary_currency: null,
				employment_type: null,
				extracted_skills: [],
				culture_text: null,
				description_snippet: null,
			},
			confirmation_token: "abc-123",
			expires_at: "2026-02-14T12:00:00Z",
		};
		expect(res.preview.job_title).toBe("Engineer");
		expect(res.confirmation_token).toBe("abc-123");
	});
});

// ---------------------------------------------------------------------------
// Compile-time type compatibility checks (no-op at runtime)
// ---------------------------------------------------------------------------

describe("type compatibility", () => {
	it("IngestSourceName is assignable from const array elements", () => {
		const name: IngestSourceName = INGEST_SOURCE_NAMES[0];
		expect(typeof name).toBe("string");
	});

	it("ExtractedSkillPreview accepts full shape", () => {
		const skill: ExtractedSkillPreview = {
			skill_name: "TypeScript",
			skill_type: "Hard",
			is_required: true,
			years_requested: 3,
		};
		expect(skill.skill_name).toBe("TypeScript");
	});

	it("IngestConfirmRequest accepts optional modifications", () => {
		const req: IngestConfirmRequest = {
			confirmation_token: "token-1",
		};
		expect(req.modifications).toBeUndefined();
	});

	it("IngestPreview allows all-null fields except extracted_skills", () => {
		const preview: IngestPreview = {
			job_title: null,
			company_name: null,
			location: null,
			salary_min: null,
			salary_max: null,
			salary_currency: null,
			employment_type: null,
			extracted_skills: [],
			culture_text: null,
			description_snippet: null,
		};
		expect(preview.extracted_skills).toEqual([]);
	});
});
