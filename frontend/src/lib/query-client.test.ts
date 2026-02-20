import { afterEach, describe, expect, it } from "vitest";

import {
	createQueryClient,
	getActiveQueryClient,
	setActiveQueryClient,
} from "./query-client";

// ---------------------------------------------------------------------------
// createQueryClient — configuration
// ---------------------------------------------------------------------------

describe("createQueryClient", () => {
	it("returns a QueryClient instance", () => {
		const client = createQueryClient();
		// QueryClient has getDefaultOptions method
		expect(client.getDefaultOptions).toBeTypeOf("function");
	});

	it("sets retry to 1 for queries", () => {
		const client = createQueryClient();
		const defaults = client.getDefaultOptions();
		expect(defaults.queries?.retry).toBe(1);
	});

	it("sets staleTime to 30 seconds for queries", () => {
		const client = createQueryClient();
		const defaults = client.getDefaultOptions();
		expect(defaults.queries?.staleTime).toBe(30_000);
	});

	it("disables refetchOnWindowFocus for queries", () => {
		const client = createQueryClient();
		const defaults = client.getDefaultOptions();
		expect(defaults.queries?.refetchOnWindowFocus).toBe(false);
	});

	it("sets retry to 0 for mutations", () => {
		const client = createQueryClient();
		const defaults = client.getDefaultOptions();
		expect(defaults.mutations?.retry).toBe(0);
	});

	it("creates independent instances on each call", () => {
		const client1 = createQueryClient();
		const client2 = createQueryClient();
		expect(client1).not.toBe(client2);
	});
});

// ---------------------------------------------------------------------------
// Active query client singleton
// ---------------------------------------------------------------------------

describe("active query client singleton", () => {
	afterEach(() => {
		// Reset singleton state between tests
		setActiveQueryClient(null);
	});

	it("returns null before any client is set", () => {
		expect(getActiveQueryClient()).toBeNull();
	});

	it("returns the client after setActiveQueryClient is called", () => {
		const client = createQueryClient();
		setActiveQueryClient(client);

		expect(getActiveQueryClient()).toBe(client);
	});

	it("replaces the previous client when set again", () => {
		const client1 = createQueryClient();
		const client2 = createQueryClient();

		setActiveQueryClient(client1);
		setActiveQueryClient(client2);

		expect(getActiveQueryClient()).toBe(client2);
	});
});
