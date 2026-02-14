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
	if (job.salary_min === null && job.salary_max === null)
		return "Not disclosed";
	const currency = job.salary_currency ?? "USD";
	const fmt = (n: number) => `$${Math.round(n / 1000)}k`;
	if (job.salary_min !== null && job.salary_max !== null) {
		return `${fmt(job.salary_min)}\u2013${fmt(job.salary_max)} ${currency}`;
	}
	if (job.salary_min !== null) return `${fmt(job.salary_min)}+ ${currency}`;
	return `Up to ${fmt(job.salary_max!)} ${currency}`;
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
