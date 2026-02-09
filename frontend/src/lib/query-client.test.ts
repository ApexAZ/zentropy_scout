import { describe, expect, it } from "vitest";

import { createQueryClient } from "./query-client";

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
