/**
 * Stateful Playwright route mock controller for settings page E2E tests.
 *
 * Uses page.route() to intercept API calls. Mock state is mutable so
 * responses evolve as the user interacts with the settings page
 * (e.g., after PATCH toggle, later GETs return updated preference).
 *
 * All API routes use a single regex to avoid Playwright glob matching
 * edge cases with cross-origin URLs.
 */

import type { Page, Route } from "@playwright/test";

import type { UserSourcePreference } from "@/types/source";

import {
	jobSourcesList,
	onboardedPersonaList,
	patchPreferenceResponse,
	userSourcePreferencesList,
} from "../fixtures/settings-mock-data";

// Re-export IDs so spec files can import from a single source
export { JOB_SOURCE_IDS, PREFERENCE_IDS } from "../fixtures/settings-mock-data";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SettingsMockState {
	/** Mutable preference overrides keyed by preference ID. */
	preferenceOverrides: Map<string, Partial<UserSourcePreference>>;
}

// ---------------------------------------------------------------------------
// Controller
// ---------------------------------------------------------------------------

export class SettingsMockController {
	state: SettingsMockState;

	constructor() {
		this.state = {
			preferenceOverrides: new Map(),
		};
	}

	async setupRoutes(page: Page): Promise<void> {
		// Abort SSE / events endpoints to prevent hanging connections
		await page.route("**/api/v1/events/**", (route) => route.abort());
		await page.route("**/api/v1/events", (route) => route.abort());

		// Mock /auth/me for AccountSection (requires session data)
		await page.route("**/api/v1/auth/me", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					data: {
						id: "00000000-0000-4000-a000-000000000001",
						email: "test@example.com",
						name: "Test User",
						image: null,
						email_verified: true,
						has_password: true,
					},
				}),
			});
		});

		// Single regex intercepts all /api/v1/ endpoints we need to mock.
		await page.route(
			/\/api\/v1\/(personas|job-sources|user-source-preferences)/,
			async (route) => this.handleRoute(route),
		);
	}

	// -----------------------------------------------------------------------
	// Main router
	// -----------------------------------------------------------------------

	private async handleRoute(route: Route): Promise<void> {
		const url = route.request().url();
		const method = route.request().method();
		const parsed = new URL(url);
		const path = parsed.pathname;

		// ---- Personas (required for persona status guard) ----
		if (path.includes("/personas")) {
			return this.json(route, onboardedPersonaList());
		}

		// ---- Job sources ----
		if (path.endsWith("/job-sources") && method === "GET") {
			return this.json(route, jobSourcesList());
		}

		// ---- User source preferences ----
		if (path.includes("/user-source-preferences")) {
			return this.handlePreferences(route, path, method);
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Preferences handler
	// -----------------------------------------------------------------------

	private async handlePreferences(
		route: Route,
		path: string,
		method: string,
	): Promise<void> {
		// PATCH /user-source-preferences/{id}
		const detailMatch = path.match(/\/user-source-preferences\/([^/]+)$/);
		if (detailMatch && method === "PATCH") {
			const prefId = detailMatch[1];
			const body = route
				.request()
				.postDataJSON() as Partial<UserSourcePreference>;
			this.state.preferenceOverrides.set(prefId, {
				...this.state.preferenceOverrides.get(prefId),
				...body,
			});
			return this.json(route, patchPreferenceResponse(prefId, body));
		}

		// GET /user-source-preferences (list)
		if (method === "GET") {
			const list = userSourcePreferencesList();
			const data = list.data.map((pref) => ({
				...pref,
				...this.state.preferenceOverrides.get(pref.id),
			}));
			return this.json(route, { data, meta: list.meta });
		}

		return route.continue();
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
 * Set up mocks for the settings page — job sources, preferences, persona guard.
 */
export async function setupSettingsMocks(
	page: Page,
): Promise<SettingsMockController> {
	const controller = new SettingsMockController();
	await controller.setupRoutes(page);
	return controller;
}
