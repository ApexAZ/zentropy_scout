/**
 * Stateful Playwright route mock controller for resume E2E tests.
 *
 * Uses page.route() to intercept API calls. Mock state is mutable so
 * responses evolve as the user interacts with resume pages
 * (e.g., after POST create, later GETs include the new resume).
 *
 * All API routes use a single regex to avoid Playwright glob matching
 * edge cases with cross-origin URLs.
 */

import type { Page, Route } from "@playwright/test";

import type { BaseResume } from "@/types/resume";

import {
	activeBaseResumesList,
	allBaseResumesList,
	certificationsList,
	educationList,
	emptyBaseResumesList,
	emptyChangeFlagsList,
	emptyChatMessages,
	jobPostingsForVariantsList,
	jobVariantsList,
	onboardedPersonaList,
	postBaseResumeResponse,
	PERSONA_ID,
	skillsList,
	workHistoryList,
} from "../fixtures/resume-mock-data";

// Re-export IDs so spec files can import from a single source
export {
	BASE_RESUME_IDS,
	JOB_VARIANT_IDS,
	PERSONA_ID,
} from "../fixtures/resume-mock-data";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ResumeMockState {
	/** Whether to include archived resumes in the list. */
	includeArchived: boolean;
	/** Whether to start with an empty resume list. */
	startEmpty: boolean;
	/** Set of archived resume IDs (removed from active list). */
	archivedResumeIds: Set<string>;
	/** Newly created resume from POST. */
	createdResume: BaseResume | null;
	/** Accumulated PATCH overrides per resume ID. */
	resumePatches: Map<string, Partial<BaseResume>>;
}

// ---------------------------------------------------------------------------
// Controller
// ---------------------------------------------------------------------------

export class ResumeMockController {
	state: ResumeMockState;

	constructor(initialState?: Partial<ResumeMockState>) {
		this.state = {
			includeArchived: false,
			startEmpty: false,
			archivedResumeIds: new Set(),
			createdResume: null,
			resumePatches: new Map(),
			...initialState,
		};
	}

	async setupRoutes(page: Page): Promise<void> {
		// Abort SSE / events endpoints to prevent hanging connections
		await page.route("**/api/v1/events/**", (route) => route.abort());
		await page.route("**/api/v1/events", (route) => route.abort());

		// Single regex intercepts all /api/v1/ endpoints we need to mock.
		await page.route(
			/\/api\/v1\/(chat|persona-change-flags|personas|base-resumes|job-variants|job-postings)/,
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

		// ---- Personas — onboarded ----
		if (path.endsWith("/personas")) {
			return this.json(route, onboardedPersonaList());
		}

		// ---- Persona sub-entities ----
		if (path.includes("/personas/")) {
			return this.handlePersonaSubEntities(route, path);
		}

		// ---- Base resumes ----
		if (path.includes("/base-resumes")) {
			return this.handleBaseResumes(route, path, method);
		}

		// ---- Job variants ----
		if (path.includes("/job-variants")) {
			return this.json(route, jobVariantsList());
		}

		// ---- Job postings (for VariantsList job lookup) ----
		if (path.includes("/job-postings")) {
			return this.json(route, jobPostingsForVariantsList());
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Persona sub-entities handler
	// -----------------------------------------------------------------------

	private async handlePersonaSubEntities(
		route: Route,
		path: string,
	): Promise<void> {
		if (path.endsWith("/work-history")) {
			return this.json(route, workHistoryList());
		}
		if (path.endsWith("/education")) {
			return this.json(route, educationList());
		}
		if (path.endsWith("/certifications")) {
			return this.json(route, certificationsList());
		}
		if (path.endsWith("/skills")) {
			return this.json(route, skillsList());
		}
		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Base resumes handler
	// -----------------------------------------------------------------------

	private async handleBaseResumes(
		route: Route,
		path: string,
		method: string,
	): Promise<void> {
		// POST /base-resumes/{id}/render — trigger PDF render
		if (path.endsWith("/render") && method === "POST") {
			const renderMatch = path.match(/\/base-resumes\/([^/]+)\/render$/);
			if (renderMatch) {
				const resumeId = renderMatch[1];
				const existing = this.state.resumePatches.get(resumeId) ?? {};
				this.state.resumePatches.set(resumeId, {
					...existing,
					rendered_at: "2026-02-15T14:00:00Z",
				});
				return this.json(route, { data: null });
			}
		}

		// GET /base-resumes/{id}/download — binary PDF
		if (path.endsWith("/download") && method === "GET") {
			return route.fulfill({
				status: 200,
				contentType: "application/pdf",
				body: Buffer.from("%PDF-1.4 mock content"),
			});
		}

		// DELETE/PATCH/GET /base-resumes/{id}
		const detailMatch = path.match(/\/base-resumes\/([^/]+)$/);

		if (detailMatch && method === "DELETE") {
			this.state.archivedResumeIds.add(detailMatch[1]);
			return this.empty(route, 204);
		}

		if (detailMatch && method === "PATCH") {
			const body = route.request().postDataJSON() as Partial<BaseResume>;
			const resumeId = detailMatch[1];
			const existing = this.state.resumePatches.get(resumeId) ?? {};
			this.state.resumePatches.set(resumeId, {
				...existing,
				...body,
				updated_at: "2026-02-15T13:00:00Z",
			});
			return this.handleResumeDetail(route, resumeId);
		}

		// POST /base-resumes — create
		if (path.endsWith("/base-resumes") && method === "POST") {
			const body = route.request().postDataJSON() as Partial<BaseResume>;
			const response = postBaseResumeResponse({
				name: body.name ?? "New Resume",
				role_type: body.role_type ?? "Software Engineer",
				summary: body.summary ?? "A new resume",
				persona_id: body.persona_id ?? PERSONA_ID,
			});
			this.state.createdResume = response.data;
			return this.json(route, response, 201);
		}

		// GET /base-resumes — list
		if (path.endsWith("/base-resumes") && method === "GET") {
			return this.json(route, this.getResumeList(route));
		}

		// GET /base-resumes/{id} — detail
		if (detailMatch && method === "GET") {
			return this.handleResumeDetail(route, detailMatch[1]);
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Resume list with archived/empty filtering
	// -----------------------------------------------------------------------

	private getResumeList(
		route: Route,
	): ReturnType<typeof activeBaseResumesList> {
		if (this.state.startEmpty) {
			return emptyBaseResumesList();
		}

		const parsed = new URL(route.request().url());
		const includeArchived =
			parsed.searchParams.get("include_archived") === "true";

		const source = includeArchived
			? allBaseResumesList()
			: activeBaseResumesList();

		// Filter out dynamically archived resumes
		if (this.state.archivedResumeIds.size > 0) {
			const filtered = source.data.filter(
				(r) => !this.state.archivedResumeIds.has(r.id),
			);
			return {
				data: filtered,
				meta: { ...source.meta, total: filtered.length },
			};
		}

		return source;
	}

	// -----------------------------------------------------------------------
	// Resume detail
	// -----------------------------------------------------------------------

	private async handleResumeDetail(
		route: Route,
		resumeId: string,
	): Promise<void> {
		const allResumes = allBaseResumesList().data;
		const resume = allResumes.find((r) => r.id === resumeId);
		if (resume) {
			const patches = this.state.resumePatches.get(resumeId);
			const merged = patches ? { ...resume, ...patches } : resume;
			return this.json(route, { data: merged });
		}
		// Check if it's the newly created resume
		if (this.state.createdResume?.id === resumeId) {
			return this.json(route, { data: this.state.createdResume });
		}
		return this.json(
			route,
			{ error: { code: "NOT_FOUND", message: "Resume not found" } },
			404,
		);
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	private async json(route: Route, body: unknown, status = 200): Promise<void> {
		await route.fulfill({
			status,
			contentType: "application/json",
			body: JSON.stringify(body),
		});
	}

	private async empty(route: Route, status = 204): Promise<void> {
		await route.fulfill({ status, body: "" });
	}
}

// ---------------------------------------------------------------------------
// Convenience factories
// ---------------------------------------------------------------------------

/**
 * Set up mocks for resume list — 2 active resumes + 1 archived,
 * 2 variants (1 Draft, 1 Approved) for the first resume.
 */
export async function setupResumeListMocks(
	page: Page,
): Promise<ResumeMockController> {
	const controller = new ResumeMockController();
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for empty resume list — no resumes at all.
 */
export async function setupEmptyResumeListMocks(
	page: Page,
): Promise<ResumeMockController> {
	const controller = new ResumeMockController({ startEmpty: true });
	await controller.setupRoutes(page);
	return controller;
}
