/**
 * Shared formatting utilities for job posting display.
 *
 * Used by OpportunitiesTable and JobDetailHeader to avoid
 * cross-file duplication of formatting logic.
 */

import type { JobPosting } from "@/types/job";

// ---------------------------------------------------------------------------
// Salary formatting
// ---------------------------------------------------------------------------

/** Format a job's salary range as a human-readable string. */
export function formatSalary(job: JobPosting): string {
	return formatSnapshotSalary(
		job.salary_min,
		job.salary_max,
		job.salary_currency,
	);
}

/** Format salary from individual fields (used by job snapshot display). */
export function formatSnapshotSalary(
	salaryMin: number | null,
	salaryMax: number | null,
	salaryCurrency: string | null,
): string {
	if (salaryMin === null && salaryMax === null) return "Not disclosed";
	const currency = salaryCurrency ?? "USD";
	const fmt = (n: number) => `$${Math.round(n / 1000)}k`;
	if (salaryMin !== null && salaryMax !== null) {
		return `${fmt(salaryMin)}\u2013${fmt(salaryMax)} ${currency}`;
	}
	if (salaryMin !== null) return `${fmt(salaryMin)}+ ${currency}`;
	return `Up to ${fmt(salaryMax!)} ${currency}`;
}

// ---------------------------------------------------------------------------
// Date formatting
// ---------------------------------------------------------------------------

/** Format a YYYY-MM-DD date string as relative days ago. */
export function formatDaysAgo(dateString: string): string {
	const [year, month, day] = dateString.split("-").map(Number);
	const jobDate = new Date(year, month - 1, day);
	const now = new Date();
	const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
	const diffMs = today.getTime() - jobDate.getTime();
	const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
	if (days === 0) return "Today";
	if (days === 1) return "1 day ago";
	return `${days} days ago`;
}

/** Format an ISO 8601 datetime string as relative days ago (UTC calendar days). */
export function formatDateTimeAgo(isoString: string): string {
	const parsed = new Date(isoString);
	const inputDate = new Date(
		Date.UTC(
			parsed.getUTCFullYear(),
			parsed.getUTCMonth(),
			parsed.getUTCDate(),
		),
	);
	const now = new Date();
	const todayUtc = new Date(
		Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()),
	);
	const diffMs = todayUtc.getTime() - inputDate.getTime();
	const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
	if (days === 0) return "Today";
	if (days === 1) return "1 day ago";
	return `${days} days ago`;
}
