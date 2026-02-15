/**
 * Stateful Playwright route mock controller for onboarding E2E tests.
 *
 * Uses page.route() to intercept API calls. Mock state is mutable so
 * responses evolve as the user progresses through onboarding steps
 * (e.g., after Step 2 submits basic info, later GETs return that data).
 */

import type { Page, Route } from "@playwright/test";

import type {
	AchievementStory,
	Bullet,
	Persona,
	Skill,
	WorkHistory,
} from "@/types/persona";

import {
	achievementStoriesList,
	certificationsList,
	customNonNegotiablesList,
	educationList,
	emptyAchievementStoriesList,
	emptyCertificationsList,
	emptyChangeFlagsList,
	emptyChatMessages,
	emptyEducationList,
	emptyPersonaList,
	emptySkillsList,
	emptyVoiceProfileResponse,
	emptyWorkHistoryList,
	PERSONA_ID,
	patchPersonaResponse,
	personaList,
	postBaseResumeResponse,
	postBulletResponse,
	postSkillResponse,
	postStoryResponse,
	postWorkHistoryResponse,
	skillsList,
	uploadResumeResponse,
	voiceProfileResponse,
	workHistoryList,
} from "../fixtures/onboarding-mock-data";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MockState {
	hasPersona: boolean;
	onboardingComplete: boolean;
	onboardingStep: string | null;
	personaPatches: Partial<Persona>;
	workHistoryCount: number;
	bulletCounts: Record<string, number>;
	skillCount: number;
	storyCount: number;
	hasEducation: boolean;
	hasCertifications: boolean;
	hasVoiceProfile: boolean;
}

// ---------------------------------------------------------------------------
// Controller
// ---------------------------------------------------------------------------

export class OnboardingMockController {
	state: MockState;

	constructor(initialState?: Partial<MockState>) {
		this.state = {
			hasPersona: false,
			onboardingComplete: false,
			onboardingStep: null,
			personaPatches: {},
			workHistoryCount: 0,
			bulletCounts: {},
			skillCount: 0,
			storyCount: 0,
			hasEducation: false,
			hasCertifications: false,
			hasVoiceProfile: false,
			...initialState,
		};
	}

	async setupRoutes(page: Page): Promise<void> {
		// Abort SSE / events endpoints to prevent hanging connections
		await page.route("**/api/v1/events/**", (route) => route.abort());
		await page.route("**/api/v1/events", (route) => route.abort());

		// Chat messages — always empty
		await page.route("**/api/v1/chat/**", (route) =>
			this.json(route, emptyChatMessages()),
		);

		// Persona change flags — always empty
		await page.route("**/api/v1/persona-change-flags", (route) =>
			this.json(route, emptyChangeFlagsList()),
		);

		// ---- Personas (list) ----
		await page.route("**/api/v1/personas", async (route) => {
			const method = route.request().method();

			if (method === "GET") {
				if (!this.state.hasPersona) {
					return this.json(route, emptyPersonaList());
				}
				return this.json(
					route,
					personaList({
						onboarding_complete: this.state.onboardingComplete,
						onboarding_step: this.state.onboardingStep,
						...this.state.personaPatches,
					}),
				);
			}

			// POST — create persona
			if (method === "POST") {
				this.state.hasPersona = true;
				return this.json(route, patchPersonaResponse({ id: PERSONA_ID }), 201);
			}

			return route.continue();
		});

		// ---- Persona PATCH / detail ----
		await page.route(`**/api/v1/personas/${PERSONA_ID}`, async (route) => {
			const method = route.request().method();

			if (method === "PATCH") {
				const body = route.request().postDataJSON() as Partial<Persona>;

				// Track checkpoint updates
				if (body.onboarding_step !== undefined) {
					this.state.onboardingStep = body.onboarding_step;
				}
				if (body.onboarding_complete !== undefined) {
					this.state.onboardingComplete = body.onboarding_complete;
				}

				// Merge persona patches for pre-fill on later steps
				this.state.personaPatches = {
					...this.state.personaPatches,
					...body,
				};
				this.state.hasPersona = true;

				return this.json(route, patchPersonaResponse(body));
			}

			if (method === "GET") {
				return this.json(
					route,
					patchPersonaResponse(this.state.personaPatches),
				);
			}

			return route.continue();
		});

		// ---- Persona refresh (Scouter trigger) ----
		await page.route(`**/api/v1/personas/${PERSONA_ID}/refresh`, (route) =>
			this.json(route, { data: null }),
		);

		// ---- Resume files ----
		await page.route("**/api/v1/resume-files", async (route) => {
			if (route.request().method() === "POST") {
				this.state.hasPersona = true;
				return this.json(route, uploadResumeResponse(), 201);
			}
			return this.json(route, this.emptyList());
		});

		// ---- Work History ----
		await page.route(
			`**/api/v1/personas/${PERSONA_ID}/work-history`,
			async (route) => {
				const method = route.request().method();

				if (method === "GET") {
					if (this.state.workHistoryCount > 0) {
						return this.json(route, workHistoryList());
					}
					return this.json(route, emptyWorkHistoryList());
				}

				if (method === "POST") {
					this.state.workHistoryCount++;
					const body = route.request().postDataJSON();
					return this.json(
						route,
						postWorkHistoryResponse(body as Partial<WorkHistory>),
						201,
					);
				}

				return route.continue();
			},
		);

		// ---- Work History PATCH (individual + bullets) ----
		await page.route(
			`**/api/v1/personas/${PERSONA_ID}/work-history/**`,
			async (route) => {
				const url = route.request().url();
				const method = route.request().method();

				// Bullet POST
				if (url.includes("/bullets") && method === "POST") {
					const whIdMatch = url.match(/work-history\/([^/]+)\/bullets/);
					const whId = whIdMatch?.[1] ?? "wh-001";
					this.state.bulletCounts[whId] =
						(this.state.bulletCounts[whId] ?? 0) + 1;
					const body = route.request().postDataJSON();
					return this.json(
						route,
						postBulletResponse(whId, body as Partial<Bullet>),
						201,
					);
				}

				// PATCH work history entry (reorder)
				if (method === "PATCH") {
					const body = route.request().postDataJSON();
					return this.json(route, { data: body });
				}

				return route.continue();
			},
		);

		// ---- Education ----
		await page.route(
			`**/api/v1/personas/${PERSONA_ID}/education`,
			async (route) => {
				const method = route.request().method();

				if (method === "GET") {
					if (this.state.hasEducation) {
						return this.json(route, educationList());
					}
					return this.json(route, emptyEducationList());
				}

				if (method === "POST") {
					this.state.hasEducation = true;
					return this.json(route, { data: { id: "edu-new" } }, 201);
				}

				return route.continue();
			},
		);

		// ---- Skills ----
		await page.route(
			`**/api/v1/personas/${PERSONA_ID}/skills`,
			async (route) => {
				const method = route.request().method();

				if (method === "GET") {
					if (this.state.skillCount > 0) {
						return this.json(route, skillsList());
					}
					return this.json(route, emptySkillsList());
				}

				if (method === "POST") {
					this.state.skillCount++;
					const body = route.request().postDataJSON();
					return this.json(
						route,
						postSkillResponse(body as Partial<Skill>),
						201,
					);
				}

				return route.continue();
			},
		);

		// ---- Skills PATCH (individual) ----
		await page.route(
			`**/api/v1/personas/${PERSONA_ID}/skills/*`,
			async (route) => {
				if (route.request().method() === "PATCH") {
					const body = route.request().postDataJSON();
					return this.json(route, { data: body });
				}
				return route.continue();
			},
		);

		// ---- Certifications ----
		await page.route(
			`**/api/v1/personas/${PERSONA_ID}/certifications`,
			async (route) => {
				const method = route.request().method();

				if (method === "GET") {
					if (this.state.hasCertifications) {
						return this.json(route, certificationsList());
					}
					return this.json(route, emptyCertificationsList());
				}

				if (method === "POST") {
					this.state.hasCertifications = true;
					return this.json(route, { data: { id: "cert-new" } }, 201);
				}

				return route.continue();
			},
		);

		// ---- Achievement Stories ----
		await page.route(
			`**/api/v1/personas/${PERSONA_ID}/achievement-stories`,
			async (route) => {
				const method = route.request().method();

				if (method === "GET") {
					if (this.state.storyCount >= 3) {
						return this.json(route, achievementStoriesList());
					}
					if (this.state.storyCount > 0) {
						const stories = achievementStoriesList();
						return this.json(route, {
							data: stories.data.slice(0, this.state.storyCount),
							meta: { ...stories.meta, total: this.state.storyCount },
						});
					}
					return this.json(route, emptyAchievementStoriesList());
				}

				if (method === "POST") {
					this.state.storyCount++;
					const body = route.request().postDataJSON();
					return this.json(
						route,
						postStoryResponse(body as Partial<AchievementStory>),
						201,
					);
				}

				return route.continue();
			},
		);

		// ---- Achievement Stories PATCH (individual) ----
		await page.route(
			`**/api/v1/personas/${PERSONA_ID}/achievement-stories/*`,
			async (route) => {
				if (route.request().method() === "PATCH") {
					const body = route.request().postDataJSON();
					return this.json(route, { data: body });
				}
				return route.continue();
			},
		);

		// ---- Voice Profile ----
		await page.route(
			`**/api/v1/personas/${PERSONA_ID}/voice-profile`,
			async (route) => {
				const method = route.request().method();

				if (method === "GET") {
					if (this.state.hasVoiceProfile) {
						return this.json(route, voiceProfileResponse());
					}
					return this.json(route, emptyVoiceProfileResponse());
				}

				if (method === "PATCH") {
					this.state.hasVoiceProfile = true;
					return this.json(route, voiceProfileResponse());
				}

				return route.continue();
			},
		);

		// ---- Custom Non-Negotiables ----
		await page.route(
			`**/api/v1/personas/${PERSONA_ID}/custom-non-negotiables`,
			(route) => this.json(route, customNonNegotiablesList()),
		);

		// ---- Base Resumes ----
		await page.route("**/api/v1/base-resumes", async (route) => {
			if (route.request().method() === "POST") {
				return this.json(route, postBaseResumeResponse(), 201);
			}
			return this.json(route, this.emptyList());
		});
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
 * Set up mocks for a brand-new user (no persona).
 * Gate tests redirect to /onboarding.
 */
export async function setupFreshUserMocks(
	page: Page,
): Promise<OnboardingMockController> {
	const controller = new OnboardingMockController({
		hasPersona: false,
	});
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for a new user starting onboarding.
 * Persona exists (created during step 1/2) but is mid-flow.
 */
export async function setupNewOnboardingMocks(
	page: Page,
): Promise<OnboardingMockController> {
	const controller = new OnboardingMockController({
		hasPersona: true,
		onboardingComplete: false,
		onboardingStep: null,
	});
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for a user resuming onboarding at a specific step.
 * Persona exists with data up to that step populated.
 */
export async function setupMidFlowMocks(
	page: Page,
	stepKey: string,
): Promise<OnboardingMockController> {
	const controller = new OnboardingMockController({
		hasPersona: true,
		onboardingComplete: false,
		onboardingStep: stepKey,
		workHistoryCount: 2,
		bulletCounts: { "wh-001": 2, "wh-002": 2 },
		skillCount: 3,
		storyCount: 3,
		hasEducation: true,
		hasCertifications: true,
		hasVoiceProfile: true,
	});
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for a fully onboarded user (dashboard access allowed).
 */
export async function setupOnboardedUserMocks(
	page: Page,
): Promise<OnboardingMockController> {
	const controller = new OnboardingMockController({
		hasPersona: true,
		onboardingComplete: true,
		onboardingStep: "base-resume",
	});
	await controller.setupRoutes(page);
	return controller;
}
