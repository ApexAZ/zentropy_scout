/**
 * Stateful Playwright route mock controller for application tracking E2E tests.
 *
 * Uses page.route() to intercept API calls. Mock state is mutable so
 * responses evolve as the user interacts with application detail pages
 * (e.g., after PATCH status transition, the app status changes).
 *
 * All API routes use a single regex to avoid Playwright glob matching
 * edge cases with cross-origin URLs.
 */

import type { Page, Route } from "@playwright/test";

import type { ApiListResponse, BulkActionResult } from "@/types/api";
import type { Application, TimelineEvent } from "@/types/application";

import {
	allApplicationsList,
	APP_002_TIMELINE_EVENTS,
	APP_IDS,
	emptyTimelineEventsList,
	onboardedPersonaList,
} from "../fixtures/app-tracking-mock-data";

// Re-export IDs so spec files can import from a single source
export { APP_IDS } from "../fixtures/app-tracking-mock-data";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AppTrackingMockState {
	/** Mutable application objects, keyed by ID. */
	applications: Map<string, Application>;
	/** Mutable timeline events, keyed by application ID. */
	timelineEvents: Map<string, TimelineEvent[]>;
	/** Counter for generating new timeline event IDs. */
	nextEventId: number;
}

// ---------------------------------------------------------------------------
// Controller
// ---------------------------------------------------------------------------

export class AppTrackingMockController {
	state: AppTrackingMockState;

	constructor() {
		// Deep-clone applications into a mutable Map
		const apps = new Map<string, Application>();
		for (const app of allApplicationsList().data) {
			apps.set(app.id, { ...app, job_snapshot: { ...app.job_snapshot } });
		}

		// Clone timeline events
		const events = new Map<string, TimelineEvent[]>();
		events.set(APP_IDS[1], [...APP_002_TIMELINE_EVENTS]);
		// Other apps: empty (we'll generate a default applied event on-demand)

		this.state = {
			applications: apps,
			timelineEvents: events,
			nextEventId: 100,
		};
	}

	async setupRoutes(page: Page): Promise<void> {
		// Abort SSE / events endpoints to prevent hanging connections
		await page.route("**/api/v1/events/**", (route) => route.abort());
		await page.route("**/api/v1/events", (route) => route.abort());

		// Single regex intercepts all /api/v1/ endpoints we need to mock.
		await page.route(
			/\/api\/v1\/(chat|persona-change-flags|personas|applications)/,
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

		// ---- Applications ----
		if (path.includes("/applications")) {
			return this.handleApplications(route, path, method, parsed);
		}

		return route.continue();
	}

	// -----------------------------------------------------------------------
	// Applications handler
	// -----------------------------------------------------------------------

	private async handleApplications(
		route: Route,
		path: string,
		method: string,
		parsed: URL,
	): Promise<void> {
		// Timeline: GET/POST /applications/{id}/timeline
		const timelineMatch = path.match(/\/applications\/([^/]+)\/timeline$/);
		if (timelineMatch) {
			const appId = timelineMatch[1];
			return this.handleTimeline(route, appId, method);
		}

		// Restore: POST /applications/{id}/restore
		const restoreMatch = path.match(/\/applications\/([^/]+)\/restore$/);
		if (restoreMatch && method === "POST") {
			const appId = restoreMatch[1];
			const app = this.state.applications.get(appId);
			if (!app) return this.json(route, { error: "Not found" }, 404);
			app.archived_at = null;
			app.updated_at = new Date().toISOString();
			return this.json(route, { data: { ...app } });
		}

		// Bulk archive: POST /applications/bulk-archive
		if (path.endsWith("/bulk-archive") && method === "POST") {
			const body = route.request().postDataJSON() as { ids: string[] };
			const now = new Date().toISOString();
			for (const id of body.ids) {
				const app = this.state.applications.get(id);
				if (app) {
					app.archived_at = now;
					app.updated_at = now;
				}
			}
			const result: BulkActionResult = {
				succeeded: body.ids,
				failed: [],
			};
			return this.json(route, { data: result });
		}

		// Application detail: GET/PATCH/DELETE /applications/{id}
		const detailMatch = path.match(/\/applications\/([^/]+)$/);
		if (detailMatch) {
			const appId = detailMatch[1];

			if (method === "GET") {
				const app = this.state.applications.get(appId);
				if (!app) return this.json(route, { error: "Not found" }, 404);
				return this.json(route, { data: { ...app } });
			}

			if (method === "PATCH") {
				const app = this.state.applications.get(appId);
				if (!app) return this.json(route, { error: "Not found" }, 404);
				const body = route.request().postDataJSON() as Record<string, unknown>;
				Object.assign(app, body);
				app.updated_at = new Date().toISOString();
				if (body.status) {
					app.status_updated_at = app.updated_at;
				}
				return this.json(route, { data: { ...app } });
			}

			if (method === "DELETE") {
				const app = this.state.applications.get(appId);
				if (app) {
					app.archived_at = new Date().toISOString();
					app.updated_at = app.archived_at;
				}
				return this.json(route, null, 204);
			}

			return route.abort();
		}

		// Applications list: GET /applications
		if (path.endsWith("/applications") && method === "GET") {
			const statusParam = parsed.searchParams.get("status");
			const includeArchived =
				parsed.searchParams.get("include_archived") === "true";

			let apps = Array.from(this.state.applications.values());

			// Filter by status
			if (statusParam) {
				const statuses = statusParam.split(",");
				apps = apps.filter((a) => statuses.includes(a.status));
			}

			// Filter out archived unless explicitly included
			if (!includeArchived) {
				apps = apps.filter((a) => a.archived_at === null);
			}

			const response: ApiListResponse<Application> = {
				data: apps.map((a) => ({ ...a })),
				meta: {
					total: apps.length,
					page: 1,
					per_page: 100,
					total_pages: 1,
				},
			};
			return this.json(route, response);
		}

		return route.abort();
	}

	// -----------------------------------------------------------------------
	// Timeline handler
	// -----------------------------------------------------------------------

	private async handleTimeline(
		route: Route,
		appId: string,
		method: string,
	): Promise<void> {
		if (method === "GET") {
			const events = this.state.timelineEvents.get(appId);
			if (!events || events.length === 0) {
				return this.json(route, emptyTimelineEventsList());
			}
			const response: ApiListResponse<TimelineEvent> = {
				data: [...events],
				meta: {
					total: events.length,
					page: 1,
					per_page: 100,
					total_pages: 1,
				},
			};
			return this.json(route, response);
		}

		if (method === "POST") {
			const body = route.request().postDataJSON() as {
				event_type: string;
				event_date: string;
				description?: string;
				interview_stage?: string;
			};
			const newEvent: TimelineEvent = {
				id: `te-new-${this.state.nextEventId++}`,
				application_id: appId,
				event_type: body.event_type as TimelineEvent["event_type"],
				event_date: body.event_date,
				description: body.description ?? null,
				interview_stage:
					(body.interview_stage as TimelineEvent["interview_stage"]) ?? null,
				created_at: new Date().toISOString(),
			};

			const existing = this.state.timelineEvents.get(appId) ?? [];
			existing.push(newEvent);
			this.state.timelineEvents.set(appId, existing);

			return this.json(route, { data: newEvent }, 201);
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
		if (status === 204) {
			await route.fulfill({
				status: 204,
				body: "",
			});
			return;
		}
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
 * Set up mocks for dedicated /applications page.
 * Good for: search, sort, select mode, bulk archive tests.
 */
export async function setupApplicationsListMocks(
	page: Page,
): Promise<AppTrackingMockController> {
	const controller = new AppTrackingMockController();
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for dashboard In Progress / History tabs.
 * Good for: tab tests, status filter, row navigation.
 */
export async function setupInProgressTabMocks(
	page: Page,
): Promise<AppTrackingMockController> {
	const controller = new AppTrackingMockController();
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for application detail page (defaults to track-app-001).
 * Good for: detail metadata, notes, pin, archive tests.
 */
export async function setupAppDetailMocks(
	page: Page,
): Promise<AppTrackingMockController> {
	const controller = new AppTrackingMockController();
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for offer application detail (track-app-003).
 * Good for: offer details card, Offer → Accepted transition.
 */
export async function setupOfferAppMocks(
	page: Page,
): Promise<AppTrackingMockController> {
	const controller = new AppTrackingMockController();
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for rejected application detail (track-app-005).
 * Good for: rejection details card.
 */
export async function setupRejectedAppMocks(
	page: Page,
): Promise<AppTrackingMockController> {
	const controller = new AppTrackingMockController();
	await controller.setupRoutes(page);
	return controller;
}

/**
 * Set up mocks for timeline application detail (track-app-002).
 * Good for: timeline events, add event, interview stage badge.
 */
export async function setupTimelineAppMocks(
	page: Page,
): Promise<AppTrackingMockController> {
	const controller = new AppTrackingMockController();
	await controller.setupRoutes(page);
	return controller;
}
