/**
 * Stateful Playwright route mock controller for cover letter review E2E tests.
 *
 * Uses page.route() to intercept API calls. Mock state is mutable so
 * responses evolve as the user interacts with the cover letter review
 * (e.g., after PATCH approve, later GETs return Approved status).
 *
 * All API routes use a single regex to avoid Playwright glob matching
 * edge cases with cross-origin URLs.
 */

import type { Page, Route } from "@playwright/test";

import type { CoverLetter } from "@/types/application";

import {
	achievementStoriesList,
	coverLetterDetail,
	coverLettersList,
	emptyChangeFlagsList,
	emptyChatMessages,
	emptyExtractedSkillsList,
	jobPostingDetail,
	onboardedPersonaList,
	SHORT_DRAFT_TEXT,
	skillsList,
	VALIDATION_WITH_ERRORS,
	VALIDATION_WITH_WARNINGS,
	voiceProfileResponse,
} from "../fixtures/cover-letter-mock-data";

// Re-export IDs so spec files can import from a single source
export {
	COVER_LETTER_ID,
	JOB_POSTING_ID,
	PERSONA_ID,
	SKILL_IDS,
	STORY_IDS,
} from "../fixtures/cover-letter-mock-data";

// Re-export fixtures for spec convenience
export {
	AGENT_REASONING,
	SHORT_DRAFT_TEXT,
	VALIDATION_WITH_ERRORS,
	VALIDATION_WITH_WARNINGS,
} from "../fixtures/cover-letter-mock-data";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CoverLetterMockState {
	/** Accumulated PATCH overrides for cover letter fields. */
	coverLetterPatches: Partial<CoverLetter>;
	/** Initial overrides applied to the base cover letter (set at construction). */
	initialOverrides: Partial<CoverLetter>;
}

// ---------------------------------------------------------------------------
// Controller
// ---------------------------------------------------------------------------

export class CoverLetterMockController {
	state: CoverLetterMockState;

	constructor(initialState?: Partial<CoverLetterMockState>) {
		this.state = {
			coverLetterPatches: {},
			initialOverrides: {},
			...initialState,
		};
	}

	async setupRoutes(page: Page): Promise<void> {
		// Abort SSE / events endpoints to prevent hanging connections
		await page.route("**/api/v1/events/**", (route) => route.abort());
		await page.route("**/api/v1/events", (route) => route.abort());

		// Single regex intercepts all /api/v1/ endpoints we need to mock.
		await page.route(
			/\/api\/v1\/(chat|persona-change-flags|personas|job-postings|cover-letters|variants|applications|submitted-cover-letter-pdfs)/,
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

		// ---- Cover letters ----
		if (path.includes("/cover-letters")) {
			return this.handleCoverLetters(route, path, method);
		}

		// ---- Submitted cover letter PDFs ----
		if (path.includes("/submitted-cover-letter-pdfs")) {
			return this.handlePdfDownload(route, path);
		}

		// ---- Variants — empty list ----
		if (path.includes("/variants")) {
			return this.json(route, { data: [], meta: this.emptyMeta() });
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
			return this.json(route, emptyExtractedSkillsList());
		}

		// GET /job-postings/{id}
		const detailMatch = path.match(/\/job-postings\/([^/]+)$/);
		if (detailMatch) {
			return this.json(route, jobPostingDetail());
		}

		return route.continue();
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
				updated_at: "2026-02-15T14:00:00Z",
			};
			if (body.status === "Approved") {
				this.state.coverLetterPatches.approved_at = "2026-02-15T14:00:00Z";
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
			return this.json(route, this.getCoverLetterList());
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
	// Cover letter state helpers
	// -----------------------------------------------------------------------

	/** Merged overrides: initial + accumulated patches. */
	private getCoverLetterOverrides(): Partial<CoverLetter> {
		return {
			...this.state.initialOverrides,
			...this.state.coverLetterPatches,
		};
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
 * Set up mocks for cover letter review — default Draft cover letter
 * with agent reasoning, stories, and voice profile.
 */
export async function setupDraftCoverLetterMocks(
	page: Page,
): Promise<CoverLetterMockController> {
	const controller = new CoverLetterMockController();
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for cover letter with validation errors (error-severity).
 */
export async function setupValidationErrorMocks(
	page: Page,
): Promise<CoverLetterMockController> {
	const controller = new CoverLetterMockController({
		initialOverrides: { validation_result: VALIDATION_WITH_ERRORS },
	});
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for cover letter with validation warnings (warning-severity).
 */
export async function setupValidationWarningMocks(
	page: Page,
): Promise<CoverLetterMockController> {
	const controller = new CoverLetterMockController({
		initialOverrides: { validation_result: VALIDATION_WITH_WARNINGS },
	});
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for cover letter with short draft text (below 250-word minimum).
 */
export async function setupShortDraftMocks(
	page: Page,
): Promise<CoverLetterMockController> {
	const controller = new CoverLetterMockController({
		initialOverrides: { draft_text: SHORT_DRAFT_TEXT },
	});
	await controller.setupRoutes(page);
	return controller;
}
