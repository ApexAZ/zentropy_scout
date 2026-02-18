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

import type { ApiListResponse } from "@/types/api";
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
	postCertificationResponse,
	postEducationResponse,
	postSkillResponse,
	postStoryResponse,
	postWorkHistoryResponse,
	resolvedChangeFlagResponse,
	skillsList,
	voiceProfileResponse,
	workHistoryList,
} from "../fixtures/persona-update-mock-data";

// Re-export IDs so spec files can import from a single source
export {
	BASE_RESUME_IDS,
	CERT_ID,
	CHANGE_FLAG_IDS,
	EDUCATION_ID,
	PERSONA_ID,
	SKILL_IDS,
	STORY_IDS,
	WORK_HISTORY_IDS,
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
	/** IDs of items deleted via the delete-with-references flow. */
	deletedItemIds: Set<string>;
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
			deletedItemIds: new Set(),
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
		// Reference check: GET /personas/{id}/{entity}/{itemId}/references
		if (path.endsWith("/references") && method === "GET") {
			return this.json(route, {
				data: {
					has_references: false,
					has_immutable_references: false,
					references: [],
				},
			});
		}

		// Delete: DELETE /personas/{id}/{entity}/{itemId}
		if (method === "DELETE") {
			const deleteMatch = path.match(
				/\/(work-history|education|certifications|skills|achievement-stories)\/([^/]+)$/,
			);
			if (deleteMatch) {
				this.state.deletedItemIds.add(deleteMatch[2]);
				await route.fulfill({ status: 204 });
				return;
			}
		}

		switch (entity) {
			case "work-history":
				if (method === "POST") {
					const body = route.request().postDataJSON() as Record<
						string,
						unknown
					>;
					return this.json(route, postWorkHistoryResponse(body), 201);
				}
				return this.json(route, this.filterDeleted(workHistoryList()));

			case "skills": {
				if (method === "POST") {
					const body = route.request().postDataJSON() as Partial<Skill>;
					const newId = `skill-new-${this.state.nextSkillId++}`;
					return this.json(
						route,
						postSkillResponse({ id: newId, ...body }),
						201,
					);
				}
				return this.json(route, this.filterDeleted(skillsList()));
			}

			case "education":
				if (method === "POST") {
					const body = route.request().postDataJSON() as Record<
						string,
						unknown
					>;
					return this.json(route, postEducationResponse(body), 201);
				}
				return this.json(route, this.filterDeleted(educationList()));

			case "certifications":
				if (method === "POST") {
					const body = route.request().postDataJSON() as Record<
						string,
						unknown
					>;
					return this.json(route, postCertificationResponse(body), 201);
				}
				return this.json(route, this.filterDeleted(certificationsList()));

			case "achievement-stories": {
				if (method === "POST") {
					const body = route.request().postDataJSON() as Record<
						string,
						unknown
					>;
					return this.json(route, postStoryResponse(body), 201);
				}
				return this.json(route, this.filterDeleted(achievementStoriesList()));
			}

			case "voice-profile": {
				if (method === "PATCH") {
					const body = route.request().postDataJSON() as Record<
						string,
						unknown
					>;
					const current = voiceProfileResponse().data;
					return this.json(route, { data: { ...current, ...body } });
				}
				return this.json(route, voiceProfileResponse());
			}

			case "custom-non-negotiables":
				return this.json(route, customNonNegotiablesList());

			case "refresh":
				return this.json(route, { data: null });

			default:
				return route.continue();
		}
	}

	// -----------------------------------------------------------------------
	// List filtering
	// -----------------------------------------------------------------------

	/** Remove deleted items from a list response. */
	private filterDeleted<T extends { id: string }>(
		response: ApiListResponse<T>,
	): ApiListResponse<T> {
		const filtered = response.data.filter(
			(item) => !this.state.deletedItemIds.has(item.id),
		);
		return {
			data: filtered,
			meta: { ...response.meta, total: filtered.length },
		};
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

/**
 * Set up mocks for persona sub-entity CRUD editors (work history, education,
 * certifications, achievement stories). Supports POST (add), DELETE (remove),
 * and reference check. Identical to overview mocks; separated for semantic
 * clarity.
 */
export const setupPersonaEditorCrudMocks = setupPersonaOverviewMocks;

/**
 * Set up mocks for achievement stories editor — stories CRUD + skill tags.
 * Identical to overview mocks; separated for semantic clarity.
 */
export const setupAchievementStoriesEditorMocks = setupPersonaOverviewMocks;

/**
 * Set up mocks for voice profile editor — form pre-fill + PATCH save.
 * Identical to overview mocks; separated for semantic clarity.
 */
export const setupVoiceProfileEditorMocks = setupPersonaOverviewMocks;
