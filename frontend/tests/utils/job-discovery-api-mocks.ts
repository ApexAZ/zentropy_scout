/**
 * Stateful Playwright route mock controller for job discovery E2E tests.
 *
 * Uses page.route() to intercept API calls. Mock state is mutable so
 * responses evolve as the user interacts with the dashboard and job detail
 * (e.g., after favoriting a job, the toggle state flips).
 *
 * All API routes use a single regex to avoid Playwright glob matching
 * edge cases with cross-origin URLs.
 */

import type { Page, Route } from "@playwright/test";

import type { BulkActionResult } from "@/types/api";

import {
	APPLICATION_ID,
	approvedCoverLetterList,
	approvedVariantList,
	applicationsList,
	emptyApplicationsList,
	emptyCoverLetterList,
	emptyVariantList,
	extractedSkillsList,
	ingestConfirmResponse,
	ingestPreviewResponse,
	jobPostingDetail,
	jobPostingsList,
	emptyJobPostingsList,
	JOB_IDS,
	onboardedPersonaList,
	postApplicationResponse,
} from "../fixtures/job-discovery-mock-data";

// Re-export IDs and factories so spec files import from a single source
export {
	APPLICATION_ID,
	expiredIngestPreviewResponse,
	INGEST_NEW_JOB_ID,
	JOB_IDS,
	PERSONA_JOB_IDS,
} from "../fixtures/job-discovery-mock-data";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MockState {
	/** How many jobs to return (0 = empty state). */
	jobCount: number;
	/** IDs that have been toggled to favorite. */
	favoriteIds: Set<string>;
	/** IDs that have been bulk-dismissed. */
	dismissedIds: Set<string>;
	/** Per-job status overrides from individual PATCH calls. */
	statusOverrides: Map<string, string>;
	/** Whether the approved variant query returns a result. */
	hasApprovedVariant: boolean;
	/** Whether the approved cover letter query returns a result. */
	hasApprovedCoverLetter: boolean;
	/** Whether an existing application exists for the job. */
	hasExistingApplication: boolean;
	/** ID of the most recently created application (null if none). */
	createdApplicationId: string | null;
}

// ---------------------------------------------------------------------------
// Controller
// ---------------------------------------------------------------------------

export class JobDiscoveryMockController {
	state: MockState;

	constructor(initialState?: Partial<MockState>) {
		this.state = {
			jobCount: 5,
			favoriteIds: new Set<string>(),
			dismissedIds: new Set<string>(),
			statusOverrides: new Map<string, string>(),
			hasApprovedVariant: false,
			hasApprovedCoverLetter: false,
			hasExistingApplication: false,
			createdApplicationId: null,
			...initialState,
		};
	}

	async setupRoutes(page: Page): Promise<void> {
		// Abort SSE / events endpoints to prevent hanging connections
		await page.route("**/api/v1/events/**", (route) => route.abort());
		await page.route("**/api/v1/events", (route) => route.abort());

		// Single regex intercepts all /api/v1/ endpoints we need to mock.
		// This avoids glob matching edge cases with cross-origin URLs.
		await page.route(
			/\/api\/v1\/(chat|persona-change-flags|personas|job-postings|variants|cover-letters|applications)/,
			async (route) => this.handleRoute(route),
		);
	}

	// -----------------------------------------------------------------------
	// Main router — dispatches by URL path
	// -----------------------------------------------------------------------

	private async handleRoute(route: Route): Promise<void> {
		const url = route.request().url();
		const method = route.request().method();
		const parsed = new URL(url);
		const path = parsed.pathname;

		// ---- Chat messages — always empty ----
		if (path.includes("/chat")) {
			return this.json(route, this.emptyList());
		}

		// ---- Persona change flags — always empty ----
		if (path.endsWith("/persona-change-flags")) {
			return this.json(route, this.emptyList());
		}

		// ---- Personas — onboarded ----
		if (path.endsWith("/personas")) {
			return this.json(route, onboardedPersonaList());
		}

		// ---- Job postings ----
		if (path.includes("/job-postings")) {
			return this.handleJobPostings(route, path, method);
		}

		// ---- Variants ----
		if (path.endsWith("/variants")) {
			return this.handleVariants(route, method, parsed);
		}

		// ---- Cover letters ----
		if (path.endsWith("/cover-letters")) {
			return this.handleCoverLetters(route, method, parsed);
		}

		// ---- Applications ----
		if (path.includes("/applications")) {
			return this.handleApplications(route, path, method);
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Job postings handler
	// -----------------------------------------------------------------------

	private async handleJobPostings(
		route: Route,
		path: string,
		method: string,
	): Promise<void> {
		// Ingest confirm: POST /job-postings/ingest/confirm
		if (path.endsWith("/ingest/confirm") && method === "POST") {
			return this.json(route, ingestConfirmResponse());
		}

		// Ingest extract: POST /job-postings/ingest
		if (path.endsWith("/ingest") && method === "POST") {
			return this.json(route, ingestPreviewResponse());
		}

		// Bulk dismiss: POST /job-postings/bulk-dismiss
		if (path.endsWith("/bulk-dismiss") && method === "POST") {
			const body = route.request().postDataJSON() as {
				ids: string[];
			};
			for (const id of body.ids) {
				this.state.dismissedIds.add(id);
			}
			const result: BulkActionResult = {
				succeeded: body.ids,
				failed: [],
			};
			return this.json(route, { data: result });
		}

		// Bulk favorite: POST /job-postings/bulk-favorite
		if (path.endsWith("/bulk-favorite") && method === "POST") {
			const body = route.request().postDataJSON() as {
				ids: string[];
				is_favorite: boolean;
			};
			for (const id of body.ids) {
				if (body.is_favorite) {
					this.state.favoriteIds.add(id);
				} else {
					this.state.favoriteIds.delete(id);
				}
			}
			const result: BulkActionResult = {
				succeeded: body.ids,
				failed: [],
			};
			return this.json(route, { data: result });
		}

		// Rescore: POST /job-postings/rescore
		if (path.endsWith("/rescore") && method === "POST") {
			return this.json(route, { data: { status: "queued" } });
		}

		// Extracted skills: GET /job-postings/{id}/extracted-skills
		if (path.includes("/extracted-skills")) {
			return this.json(route, extractedSkillsList());
		}

		// Job detail / PATCH: /job-postings/{id}
		const detailMatch = path.match(/\/job-postings\/([^/]+)$/);
		if (detailMatch) {
			const jobId = detailMatch[1];

			if (method === "GET") {
				const detail = jobPostingDetail(jobId);
				if (this.state.favoriteIds.has(jobId)) {
					detail.data.is_favorite = !detail.data.is_favorite;
				}
				const overrideStatus = this.state.statusOverrides.get(jobId);
				if (overrideStatus) {
					Object.assign(detail.data, { status: overrideStatus });
				}
				return this.json(route, detail);
			}

			if (method === "PATCH") {
				const body = route.request().postDataJSON() as Record<string, unknown>;
				if (body.is_favorite !== undefined) {
					if (body.is_favorite) {
						this.state.favoriteIds.add(jobId);
					} else {
						this.state.favoriteIds.delete(jobId);
					}
				}
				if (typeof body.status === "string") {
					this.state.statusOverrides.set(jobId, body.status);
				}
				const detail = jobPostingDetail(jobId);
				return this.json(route, {
					data: { ...detail.data, ...body },
				});
			}

			return route.abort();
		}

		// Job postings list: GET /job-postings
		if (path.endsWith("/job-postings") && method === "GET") {
			if (this.state.jobCount === 0) {
				return this.json(route, emptyJobPostingsList());
			}
			const list = jobPostingsList();
			list.data = list.data.filter((j) => !this.state.dismissedIds.has(j.id));
			for (const job of list.data) {
				if (this.state.favoriteIds.has(job.id)) {
					job.is_favorite = !job.is_favorite;
				}
			}
			// Apply individual status overrides and filter dismissed
			list.data = list.data.filter((j) => {
				const override = this.state.statusOverrides.get(j.id);
				if (override === "Dismissed") return false;
				if (override) Object.assign(j, { status: override });
				return true;
			});
			list.meta.total = list.data.length;
			return this.json(route, list);
		}

		return route.abort();
	}

	// -----------------------------------------------------------------------
	// Variants handler
	// -----------------------------------------------------------------------

	private async handleVariants(
		route: Route,
		method: string,
		parsed: URL,
	): Promise<void> {
		if (method === "GET") {
			if (this.state.hasApprovedVariant) {
				const jobId = parsed.searchParams.get("job_posting_id") ?? JOB_IDS[0];
				return this.json(route, approvedVariantList(jobId));
			}
			return this.json(route, emptyVariantList());
		}
		return route.abort();
	}

	// -----------------------------------------------------------------------
	// Cover letters handler
	// -----------------------------------------------------------------------

	private async handleCoverLetters(
		route: Route,
		method: string,
		parsed: URL,
	): Promise<void> {
		if (method === "GET") {
			if (this.state.hasApprovedCoverLetter) {
				const jobId = parsed.searchParams.get("job_posting_id") ?? JOB_IDS[0];
				return this.json(route, approvedCoverLetterList(jobId));
			}
			return this.json(route, emptyCoverLetterList());
		}
		return route.abort();
	}

	// -----------------------------------------------------------------------
	// Applications handler
	// -----------------------------------------------------------------------

	private async handleApplications(
		route: Route,
		path: string,
		method: string,
	): Promise<void> {
		// Application detail: GET /applications/{id}
		const detailMatch = path.match(/\/applications\/([^/]+)$/);
		if (detailMatch && method === "GET") {
			if (this.state.hasExistingApplication) {
				const list = applicationsList();
				return this.json(route, { data: list.data[0] });
			}
			return this.json(route, { data: null }, 404);
		}

		// Applications list: GET /applications
		if (path.endsWith("/applications") && method === "GET") {
			if (this.state.hasExistingApplication) {
				return this.json(route, applicationsList());
			}
			return this.json(route, emptyApplicationsList());
		}

		// Create application: POST /applications
		if (path.endsWith("/applications") && method === "POST") {
			const body = route.request().postDataJSON() as {
				job_posting_id: string;
			};
			this.state.createdApplicationId = APPLICATION_ID;
			this.state.hasExistingApplication = true;
			return this.json(
				route,
				postApplicationResponse(body.job_posting_id),
				201,
			);
		}

		return route.abort();
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	private emptyList(): {
		data: never[];
		meta: { total: 0; page: 1; per_page: 100; total_pages: 1 };
	} {
		return {
			data: [],
			meta: { total: 0, page: 1, per_page: 100, total_pages: 1 },
		};
	}

	private async json(route: Route, body: unknown, status = 200): Promise<void> {
		await route.fulfill({
			status,
			contentType: "application/json",
			body: JSON.stringify(body),
		});
	}
}

// ---------------------------------------------------------------------------
// Convenience factories
// ---------------------------------------------------------------------------

/**
 * Set up mocks for the dashboard with 5 jobs, no variant/app data.
 * Good for: dashboard loading, opportunities table, navigation tests.
 */
export async function setupDashboardMocks(
	page: Page,
): Promise<JobDiscoveryMockController> {
	const controller = new JobDiscoveryMockController({
		jobCount: 5,
		hasApprovedVariant: false,
		hasApprovedCoverLetter: false,
		hasExistingApplication: false,
	});
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for job detail page with approved variant + cover letter.
 * Good for: mark-as-applied card, download links, confirm applied.
 */
export async function setupJobDetailMocks(
	page: Page,
): Promise<JobDiscoveryMockController> {
	const controller = new JobDiscoveryMockController({
		jobCount: 5,
		hasApprovedVariant: true,
		hasApprovedCoverLetter: true,
		hasExistingApplication: false,
	});
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks where job already has an existing application.
 * Good for: "Already applied" notice test.
 */
export async function setupAlreadyAppliedMocks(
	page: Page,
): Promise<JobDiscoveryMockController> {
	const controller = new JobDiscoveryMockController({
		jobCount: 5,
		hasApprovedVariant: true,
		hasApprovedCoverLetter: true,
		hasExistingApplication: true,
	});
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for the Add Job modal two-step ingest flow.
 * Good for: form submission, preview display, countdown, confirm & save.
 * Currently identical to dashboard mocks; separated for semantic clarity
 * and future divergence (e.g., different initial state).
 */
export const setupAddJobMocks = setupDashboardMocks;
