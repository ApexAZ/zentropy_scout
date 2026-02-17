/**
 * Tests for job formatting utilities.
 *
 * Covers formatSalary, formatDaysAgo, and formatDateTimeAgo —
 * shared formatting helpers used by OpportunitiesTable and
 * ApplicationsTable components.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
	formatDateTimeAgo,
	formatDaysAgo,
	formatSalary,
	formatSnapshotSalary,
} from "./job-formatters";
import type { JobPosting } from "@/types/job";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeJob(overrides?: Partial<JobPosting>): JobPosting {
	return {
		id: "job-1",
		persona_id: "p-1",
		external_id: null,
		source_id: "src-1",
		also_found_on: { sources: [] },
		job_title: "Software Engineer",
		company_name: "Acme",
		company_url: null,
		source_url: null,
		apply_url: null,
		location: "Austin, TX",
		work_model: "Remote",
		seniority_level: "Mid",
		salary_min: 120000,
		salary_max: 150000,
		salary_currency: "USD",
		description: "Job description",
		culture_text: null,
		requirements: null,
		years_experience_min: null,
		years_experience_max: null,
		posted_date: null,
		application_deadline: null,
		first_seen_date: "2026-02-10",
		status: "Discovered",
		is_favorite: false,
		fit_score: 85,
		stretch_score: 65,
		score_details: null,
		failed_non_negotiables: null,
		ghost_score: 10,
		ghost_signals: null,
		description_hash: "abc123",
		repost_count: 0,
		previous_posting_ids: null,
		last_verified_at: null,
		dismissed_at: null,
		expired_at: null,
		created_at: "2026-02-10T12:00:00Z",
		updated_at: "2026-02-10T12:00:00Z",
		...overrides,
	} as JobPosting;
}

// ---------------------------------------------------------------------------
// formatSalary
// ---------------------------------------------------------------------------

describe("formatSalary", () => {
	it("formats min-max salary range", () => {
		const job = makeJob({
			salary_min: 120000,
			salary_max: 150000,
			salary_currency: "USD",
		});
		expect(formatSalary(job)).toBe("$120k\u2013$150k USD");
	});

	it("returns 'Not disclosed' when both min and max are null", () => {
		const job = makeJob({ salary_min: null, salary_max: null });
		expect(formatSalary(job)).toBe("Not disclosed");
	});

	it("formats min-only salary with plus sign", () => {
		const job = makeJob({
			salary_min: 100000,
			salary_max: null,
			salary_currency: "USD",
		});
		expect(formatSalary(job)).toBe("$100k+ USD");
	});

	it("formats max-only salary with 'Up to'", () => {
		const job = makeJob({
			salary_min: null,
			salary_max: 200000,
			salary_currency: "USD",
		});
		expect(formatSalary(job)).toBe("Up to $200k USD");
	});
});

// ---------------------------------------------------------------------------
// formatSnapshotSalary
// ---------------------------------------------------------------------------

describe("formatSnapshotSalary", () => {
	it("returns 'Not disclosed' when both min and max are null", () => {
		expect(formatSnapshotSalary(null, null, undefined)).toBe("Not disclosed");
	});

	it("formats min-max salary range", () => {
		expect(formatSnapshotSalary(120000, 150000, "USD")).toBe(
			"$120k\u2013$150k USD",
		);
	});

	it("formats min-only salary with plus sign", () => {
		expect(formatSnapshotSalary(120000, null, "USD")).toBe("$120k+ USD");
	});

	it("formats max-only salary with 'Up to'", () => {
		expect(formatSnapshotSalary(null, 150000, "USD")).toBe("Up to $150k USD");
	});

	it("defaults to USD when currency is omitted", () => {
		expect(formatSnapshotSalary(100000, 130000)).toBe("$100k\u2013$130k USD");
	});

	it("uses custom currency when provided", () => {
		expect(formatSnapshotSalary(80000, 100000, "EUR")).toBe(
			"$80k\u2013$100k EUR",
		);
	});
});

// ---------------------------------------------------------------------------
// formatDaysAgo
// ---------------------------------------------------------------------------

describe("formatDaysAgo", () => {
	it("returns 'Today' for today's date", () => {
		const now = new Date();
		const y = now.getFullYear();
		const m = String(now.getMonth() + 1).padStart(2, "0");
		const d = String(now.getDate()).padStart(2, "0");
		expect(formatDaysAgo(`${y}-${m}-${d}`)).toBe("Today");
	});

	it("returns '1 day ago' for yesterday", () => {
		const yesterday = new Date();
		yesterday.setDate(yesterday.getDate() - 1);
		const y = yesterday.getFullYear();
		const m = String(yesterday.getMonth() + 1).padStart(2, "0");
		const d = String(yesterday.getDate()).padStart(2, "0");
		expect(formatDaysAgo(`${y}-${m}-${d}`)).toBe("1 day ago");
	});
});

// ---------------------------------------------------------------------------
// formatDateTimeAgo
// ---------------------------------------------------------------------------

describe("formatDateTimeAgo", () => {
	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date("2026-02-14T15:00:00Z"));
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("returns 'Today' for a datetime earlier today", () => {
		expect(formatDateTimeAgo("2026-02-14T08:30:00Z")).toBe("Today");
	});

	it("returns '1 day ago' for yesterday's datetime", () => {
		expect(formatDateTimeAgo("2026-02-13T10:00:00Z")).toBe("1 day ago");
	});

	it("returns 'X days ago' for multiple days", () => {
		expect(formatDateTimeAgo("2026-02-09T12:00:00Z")).toBe("5 days ago");
	});

	it("handles midnight boundary correctly", () => {
		// Set system time to just after midnight
		vi.setSystemTime(new Date("2026-02-14T00:05:00Z"));
		// A datetime from the previous calendar day
		expect(formatDateTimeAgo("2026-02-13T23:55:00Z")).toBe("1 day ago");
	});
});
