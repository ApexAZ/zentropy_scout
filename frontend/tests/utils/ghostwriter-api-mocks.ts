/**
 * Stateful Playwright route mock controller for ghostwriter review E2E tests.
 *
 * Handles both resume variant and cover letter endpoints for the unified
 * ghostwriter review page (/jobs/[id]/review). Mock state tracks approval
 * status for both materials independently — variant via POST approve,
 * cover letter via PATCH status change.
 *
 * All API routes use a single regex to avoid Playwright glob matching
 * edge cases with cross-origin URLs.
 */

import type { Page, Route } from "@playwright/test";

import type { CoverLetter } from "@/types/application";
import type { JobVariant } from "@/types/resume";

import {
	achievementStoriesList,
	baseResumeDetail,
	coverLetterDetail,
	coverLettersList,
	emptyChangeFlagsList,
	emptyChatMessages,
	emptyCoverLettersList,
	emptyVariantsList,
	GUARDRAIL_WITH_ERRORS,
	jobPostingDetail,
	onboardedPersonaList,
	skillsList,
	VALIDATION_WITH_ERRORS,
	variantDetail,
	variantsList,
	voiceProfileResponse,
	workHistoryList,
} from "../fixtures/ghostwriter-mock-data";

// Re-export IDs so spec files can import from a single source
export {
	COVER_LETTER_ID,
	JOB_POSTING_ID,
	PERSONA_ID,
	VARIANT_ID,
} from "../fixtures/ghostwriter-mock-data";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Timestamp used for approval mutations in mock responses. */
const UPDATED_TIMESTAMP = "2026-02-15T14:00:00Z";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GhostwriterMockState {
	/** Whether the variant has been approved via POST. */
	variantApproved: boolean;
	/** Accumulated PATCH overrides for cover letter fields. */
	coverLetterPatches: Partial<CoverLetter>;
	/** Whether the variant has guardrail error-severity violations. */
	variantGuardrailErrors: boolean;
	/** Whether the cover letter has validation error-severity issues. */
	coverLetterValidationErrors: boolean;
	/** Whether materials (variant + cover letter) exist for the job. */
	hasMaterials: boolean;
}

// ---------------------------------------------------------------------------
// Controller
// ---------------------------------------------------------------------------

export class GhostwriterMockController {
	state: GhostwriterMockState;

	constructor(initialState?: Partial<GhostwriterMockState>) {
		this.state = {
			variantApproved: false,
			coverLetterPatches: {},
			variantGuardrailErrors: false,
			coverLetterValidationErrors: false,
			hasMaterials: true,
			...initialState,
		};
	}

	async setupRoutes(page: Page): Promise<void> {
		// Abort SSE / events endpoints to prevent hanging connections
		await page.route("**/api/v1/events/**", (route) => route.abort());
		await page.route("**/api/v1/events", (route) => route.abort());

		// Single regex intercepts all /api/v1/ endpoints we need to mock.
		await page.route(
			/\/api\/v1\/(chat|persona-change-flags|personas|job-postings|cover-letters|variants|job-variants|base-resumes|applications|submitted-cover-letter-pdfs)/,
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
			return this.json(route, emptyChatMessages());
		}

		// ---- Persona change flags — always empty ----
		if (path.endsWith("/persona-change-flags")) {
			return this.json(route, emptyChangeFlagsList());
		}

		// ---- Personas ----
		if (path.includes("/personas")) {
			return this.handlePersonas(route, path);
		}

		// ---- Job postings ----
		if (path.includes("/job-postings")) {
			return this.handleJobPostings(route, path);
		}

		// ---- Job variants (detail + approve) — BEFORE /variants (more specific) ----
		if (path.includes("/job-variants")) {
			return this.handleJobVariants(route, path, method);
		}

		// ---- Cover letters ----
		if (path.includes("/cover-letters")) {
			return this.handleCoverLetters(route, path, method);
		}

		// ---- Submitted cover letter PDFs ----
		if (path.includes("/submitted-cover-letter-pdfs")) {
			return this.handlePdfDownload(route, path);
		}

		// ---- Variants list (used by page to find materials for a job) ----
		if (path.includes("/variants")) {
			return this.handleVariantsList(route);
		}

		// ---- Base resumes ----
		if (path.includes("/base-resumes")) {
			return this.handleBaseResumes(route, path);
		}

		// ---- Applications — empty list ----
		if (path.includes("/applications")) {
			return this.json(route, { data: [], meta: this.emptyMeta() });
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Personas handler
	// -----------------------------------------------------------------------

	private async handlePersonas(route: Route, path: string): Promise<void> {
		// Sub-entity routes: /personas/{id}/{sub-entity}
		if (path.endsWith("/achievement-stories")) {
			return this.json(route, achievementStoriesList());
		}
		if (path.endsWith("/skills")) {
			return this.json(route, skillsList());
		}
		if (path.endsWith("/voice-profile")) {
			return this.json(route, voiceProfileResponse());
		}
		if (path.endsWith("/work-history")) {
			return this.json(route, workHistoryList());
		}

		// List: GET /personas
		if (path.endsWith("/personas")) {
			return this.json(route, onboardedPersonaList());
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Job postings handler
	// -----------------------------------------------------------------------

	private async handleJobPostings(route: Route, path: string): Promise<void> {
		// GET /job-postings/{id}/extracted-skills
		if (path.endsWith("/extracted-skills")) {
			return this.json(route, { data: [], meta: this.emptyMeta() });
		}

		// GET /job-postings/{id}
		const detailMatch = path.match(/\/job-postings\/([^/]+)$/);
		if (detailMatch) {
			return this.json(route, jobPostingDetail());
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Job variants handler (detail + approve)
	// -----------------------------------------------------------------------

	private async handleJobVariants(
		route: Route,
		path: string,
		method: string,
	): Promise<void> {
		// POST /job-variants/{id}/approve
		if (path.endsWith("/approve") && method === "POST") {
			this.state.variantApproved = true;
			return this.json(route, this.getVariantDetail());
		}

		// GET /job-variants/{id}
		const detailMatch = path.match(/\/job-variants\/([^/]+)$/);
		if (detailMatch && method === "GET") {
			return this.json(route, this.getVariantDetail());
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Variants list handler (used by page to find materials for a job)
	// -----------------------------------------------------------------------

	private async handleVariantsList(route: Route): Promise<void> {
		if (!this.state.hasMaterials) {
			return this.json(route, emptyVariantsList());
		}
		return this.json(route, variantsList(this.getVariantOverrides()));
	}

	// -----------------------------------------------------------------------
	// Cover letters handler
	// -----------------------------------------------------------------------

	private async handleCoverLetters(
		route: Route,
		path: string,
		method: string,
	): Promise<void> {
		// PATCH /cover-letters/{id} — approve
		const detailMatch = path.match(/\/cover-letters\/([^/]+)$/);
		if (detailMatch && method === "PATCH") {
			const body = route.request().postDataJSON() as Partial<CoverLetter>;
			this.state.coverLetterPatches = {
				...this.state.coverLetterPatches,
				...body,
				updated_at: UPDATED_TIMESTAMP,
			};
			if (body.status === "Approved") {
				this.state.coverLetterPatches.approved_at = UPDATED_TIMESTAMP;
				this.state.coverLetterPatches.final_text =
					this.getCoverLetterOverrides().draft_text ?? "";
			}
			return this.json(route, this.getCoverLetterDetail());
		}

		// GET /cover-letters/{id} — detail
		if (detailMatch && method === "GET") {
			return this.json(route, this.getCoverLetterDetail());
		}

		// GET /cover-letters — list
		if (path.endsWith("/cover-letters") && method === "GET") {
			if (!this.state.hasMaterials) {
				return this.json(route, emptyCoverLettersList());
			}
			return this.json(route, this.getCoverLetterList());
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Base resumes handler
	// -----------------------------------------------------------------------

	private async handleBaseResumes(route: Route, path: string): Promise<void> {
		const detailMatch = path.match(/\/base-resumes\/([^/]+)$/);
		if (detailMatch) {
			return this.json(route, baseResumeDetail());
		}
		return route.continue();
	}

	// -----------------------------------------------------------------------
	// PDF download handler
	// -----------------------------------------------------------------------

	private async handlePdfDownload(route: Route, path: string): Promise<void> {
		if (path.endsWith("/download")) {
			return route.fulfill({
				status: 200,
				contentType: "application/pdf",
				body: Buffer.from("%PDF-1.4 mock cover letter content"),
			});
		}
		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Variant state helpers
	// -----------------------------------------------------------------------

	private getVariantOverrides(): Partial<JobVariant> {
		const overrides: Partial<JobVariant> = {};
		if (this.state.variantApproved) {
			overrides.status = "Approved";
			overrides.approved_at = UPDATED_TIMESTAMP;
		}
		if (this.state.variantGuardrailErrors) {
			overrides.guardrail_result = GUARDRAIL_WITH_ERRORS;
		}
		return overrides;
	}

	private getVariantDetail() {
		return variantDetail(this.getVariantOverrides());
	}

	// -----------------------------------------------------------------------
	// Cover letter state helpers
	// -----------------------------------------------------------------------

	private getCoverLetterOverrides(): Partial<CoverLetter> {
		const overrides: Partial<CoverLetter> = {
			...this.state.coverLetterPatches,
		};
		if (this.state.coverLetterValidationErrors) {
			overrides.validation_result = VALIDATION_WITH_ERRORS;
		}
		return overrides;
	}

	private getCoverLetterDetail() {
		return coverLetterDetail(this.getCoverLetterOverrides());
	}

	private getCoverLetterList() {
		return coverLettersList(this.getCoverLetterOverrides());
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	private emptyMeta() {
		return { total: 0, page: 1, per_page: 100, total_pages: 1 };
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
 * Set up mocks for ghostwriter review — default Draft variant + cover letter
 * with agent reasoning, side-by-side diff data, and unified approve actions.
 */
export async function setupGhostwriterReviewMocks(
	page: Page,
): Promise<GhostwriterMockController> {
	const controller = new GhostwriterMockController();
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks with guardrail error-severity violations on the variant.
 * Approve Both and Approve Resume Only are disabled; Approve Letter Only enabled.
 */
export async function setupGuardrailErrorMocks(
	page: Page,
): Promise<GhostwriterMockController> {
	const controller = new GhostwriterMockController({
		variantGuardrailErrors: true,
	});
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks with no materials found for the job (empty variants + cover letters).
 * Page shows "No materials found" empty state.
 */
export async function setupNoMaterialsMocks(
	page: Page,
): Promise<GhostwriterMockController> {
	const controller = new GhostwriterMockController({
		hasMaterials: false,
	});
	await controller.setupRoutes(page);
	return controller;
}
