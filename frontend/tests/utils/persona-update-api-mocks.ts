/**
 * Stateful Playwright route mock controller for persona update E2E tests.
 *
 * Uses page.route() to intercept API calls. Mock state is mutable so
 * responses evolve as the user interacts with persona editors
 * (e.g., after PATCH, later GETs return updated data).
 *
 * All API routes use a single regex to avoid Playwright glob matching
 * edge cases with cross-origin URLs.
 */

import type { Page, Route } from "@playwright/test";

import type { Persona, PersonaChangeFlag, Skill } from "@/types/persona";

import {
	achievementStoriesList,
	baseResumesList,
	certificationsList,
	changeFlagsList,
	customNonNegotiablesList,
	educationList,
	emptyChatMessages,
	emptyChangeFlagsList,
	onboardedPersonaList,
	patchPersonaResponse,
	postSkillResponse,
	resolvedChangeFlagResponse,
	skillsList,
	voiceProfileResponse,
	workHistoryList,
} from "../fixtures/persona-update-mock-data";

// Re-export IDs so spec files can import from a single source
export {
	PERSONA_ID,
	CHANGE_FLAG_IDS,
	BASE_RESUME_IDS,
	SKILL_IDS,
} from "../fixtures/persona-update-mock-data";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PersonaUpdateMockState {
	/** Accumulated PATCH overrides for persona fields. */
	personaPatches: Partial<Persona>;
	/** Whether pending change flags exist. */
	hasPendingFlags: boolean;
	/** Mutable set of resolved flag IDs (removed from pending list). */
	resolvedFlagIds: Set<string>;
	/** Whether to include skills in sub-entity responses. */
	hasSkills: boolean;
	/** Counter for new skill IDs. */
	nextSkillId: number;
}

// ---------------------------------------------------------------------------
// Controller
// ---------------------------------------------------------------------------

export class PersonaUpdateMockController {
	state: PersonaUpdateMockState;

	constructor(initialState?: Partial<PersonaUpdateMockState>) {
		this.state = {
			personaPatches: {},
			hasPendingFlags: false,
			resolvedFlagIds: new Set(),
			hasSkills: true,
			nextSkillId: 100,
			...initialState,
		};
	}

	async setupRoutes(page: Page): Promise<void> {
		// Abort SSE / events endpoints to prevent hanging connections
		await page.route("**/api/v1/events/**", (route) => route.abort());
		await page.route("**/api/v1/events", (route) => route.abort());

		// Single regex intercepts all /api/v1/ endpoints we need to mock.
		await page.route(
			/\/api\/v1\/(chat|persona-change-flags|personas|base-resumes)/,
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

		// ---- Persona change flags ----
		if (path.includes("/persona-change-flags")) {
			return this.handleChangeFlags(route, path, method);
		}

		// ---- Base resumes ----
		if (path.endsWith("/base-resumes")) {
			return this.json(route, baseResumesList());
		}

		// ---- Personas + sub-entities ----
		if (path.includes("/personas")) {
			return this.handlePersonas(route, path, method);
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Persona change flags handler
	// -----------------------------------------------------------------------

	private async handleChangeFlags(
		route: Route,
		path: string,
		method: string,
	): Promise<void> {
		// PATCH /persona-change-flags/{id}
		const detailMatch = path.match(/\/persona-change-flags\/([^/]+)$/);
		if (detailMatch && method === "PATCH") {
			const flagId = detailMatch[1];
			const body = route.request().postDataJSON() as {
				status: string;
				resolution: string;
			};
			this.state.resolvedFlagIds.add(flagId);
			return this.json(
				route,
				resolvedChangeFlagResponse(
					flagId,
					body.resolution as PersonaChangeFlag["resolution"] & string,
				),
			);
		}

		// GET /persona-change-flags (list)
		if (method === "GET") {
			if (!this.state.hasPendingFlags) {
				return this.json(route, emptyChangeFlagsList());
			}
			const allFlags = changeFlagsList();
			const pendingFlags = allFlags.data.filter(
				(f) => !this.state.resolvedFlagIds.has(f.id),
			);
			return this.json(route, {
				data: pendingFlags,
				meta: {
					total: pendingFlags.length,
					page: 1,
					per_page: 100,
					total_pages: 1,
				},
			});
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Personas handler
	// -----------------------------------------------------------------------

	private async handlePersonas(
		route: Route,
		path: string,
		method: string,
	): Promise<void> {
		// Sub-entity routes: /personas/{id}/{sub-entity}
		const subEntityMatch = path.match(
			/\/personas\/[^/]+\/(work-history|skills|education|certifications|achievement-stories|voice-profile|custom-non-negotiables|refresh)/,
		);
		if (subEntityMatch) {
			return this.handleSubEntities(route, path, method, subEntityMatch[1]);
		}

		// Detail: GET/PATCH /personas/{id}
		const detailMatch = path.match(/\/personas\/([^/]+)$/);
		if (detailMatch) {
			if (method === "PATCH") {
				const body = route.request().postDataJSON() as Partial<Persona>;
				this.state.personaPatches = {
					...this.state.personaPatches,
					...body,
				};
			}
			if (method === "GET" || method === "PATCH") {
				return this.json(
					route,
					patchPersonaResponse({
						onboarding_complete: true,
						onboarding_step: "base-resume",
						...this.state.personaPatches,
					}),
				);
			}
			return route.continue();
		}

		// List: GET /personas
		if (path.endsWith("/personas") && method === "GET") {
			return this.json(route, onboardedPersonaList(this.state.personaPatches));
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Sub-entity handler
	// -----------------------------------------------------------------------

	private async handleSubEntities(
		route: Route,
		path: string,
		method: string,
		entity: string,
	): Promise<void> {
		switch (entity) {
			case "work-history":
				return this.json(route, workHistoryList());

			case "skills": {
				// POST /personas/{id}/skills
				if (method === "POST") {
					const body = route.request().postDataJSON() as Partial<Skill>;
					const newId = `skill-new-${this.state.nextSkillId++}`;
					return this.json(
						route,
						postSkillResponse({ id: newId, ...body }),
						201,
					);
				}
				// GET /personas/{id}/skills
				return this.json(route, skillsList());
			}

			case "education":
				return this.json(route, educationList());

			case "certifications":
				return this.json(route, certificationsList());

			case "achievement-stories":
				return this.json(route, achievementStoriesList());

			case "voice-profile":
				return this.json(route, voiceProfileResponse());

			case "custom-non-negotiables":
				return this.json(route, customNonNegotiablesList());

			case "refresh":
				return this.json(route, { data: null });

			default:
				return route.continue();
		}
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
}

// ---------------------------------------------------------------------------
// Convenience factories
// ---------------------------------------------------------------------------

/**
 * Set up mocks for persona overview — full persona with sub-entities,
 * no pending change flags.
 */
export async function setupPersonaOverviewMocks(
	page: Page,
): Promise<PersonaUpdateMockController> {
	const controller = new PersonaUpdateMockController({
		hasPendingFlags: false,
	});
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for persona overview with 3 pending change flags.
 */
export async function setupPersonaOverviewWithFlagsMocks(
	page: Page,
): Promise<PersonaUpdateMockController> {
	const controller = new PersonaUpdateMockController({
		hasPendingFlags: true,
	});
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for basic info editor — persona loaded for form pre-fill.
 */
export async function setupBasicInfoEditorMocks(
	page: Page,
): Promise<PersonaUpdateMockController> {
	const controller = new PersonaUpdateMockController({
		hasPendingFlags: false,
	});
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for growth targets editor — persona loaded for form pre-fill.
 */
export async function setupGrowthTargetsEditorMocks(
	page: Page,
): Promise<PersonaUpdateMockController> {
	const controller = new PersonaUpdateMockController({
		hasPendingFlags: false,
	});
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for skills editor — persona + skills for CRUD testing.
 */
export async function setupSkillsEditorMocks(
	page: Page,
): Promise<PersonaUpdateMockController> {
	const controller = new PersonaUpdateMockController({
		hasPendingFlags: false,
	});
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for change flags resolver — 3 pending flags + 2 base resumes.
 */
export async function setupChangeFlagsResolverMocks(
	page: Page,
): Promise<PersonaUpdateMockController> {
	const controller = new PersonaUpdateMockController({
		hasPendingFlags: true,
	});
	await controller.setupRoutes(page);
	return controller;
}
