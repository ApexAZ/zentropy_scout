/**
 * Tests for the SSE-to-TanStack-Query bridge.
 *
 * REQ-012 §4.2.1: data_changed SSE events invalidate corresponding
 * TanStack Query cache entries. Reconnection triggers full invalidation.
 */

import type { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
	RESOURCE_QUERY_KEY_MAP,
	createSSEQueryBridge,
	handleDataChanged,
	handleReconnect,
} from "./sse-query-bridge";
import { queryKeys } from "./query-keys";

// ---------------------------------------------------------------------------
// Test constants
// ---------------------------------------------------------------------------

const RESOURCE_JOB_POSTING = "job-posting";
const RESOURCE_COVER_LETTER = "cover-letter";
const RESOURCE_CHANGE_FLAG = "change-flag";
const RESOURCE_EMBEDDING = "embedding";
const ACTION_UPDATED = "updated";
const ACTION_CREATED = "created";
const ACTION_DELETED = "deleted";
const TEST_ID = "test-id";

// ---------------------------------------------------------------------------
// Mock QueryClient
// ---------------------------------------------------------------------------

function createMockQueryClient(): QueryClient {
	return {
		invalidateQueries: vi.fn().mockResolvedValue(undefined),
	} as unknown as QueryClient;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SSE Query Bridge", () => {
	let queryClient: QueryClient;

	beforeEach(() => {
		queryClient = createMockQueryClient();
	});

	// -----------------------------------------------------------------------
	// RESOURCE_QUERY_KEY_MAP
	// -----------------------------------------------------------------------

	describe("RESOURCE_QUERY_KEY_MAP", () => {
		it("maps persona to personas query key", () => {
			expect(RESOURCE_QUERY_KEY_MAP.get("persona")).toEqual(queryKeys.personas);
		});

		it("maps job-posting to jobs query key", () => {
			expect(RESOURCE_QUERY_KEY_MAP.get(RESOURCE_JOB_POSTING)).toEqual(
				queryKeys.jobs,
			);
		});

		it("maps application to applications query key", () => {
			expect(RESOURCE_QUERY_KEY_MAP.get("application")).toEqual(
				queryKeys.applications,
			);
		});

		it("maps resume to resumes query key", () => {
			expect(RESOURCE_QUERY_KEY_MAP.get("resume")).toEqual(queryKeys.resumes);
		});

		it("maps variant to variants query key", () => {
			expect(RESOURCE_QUERY_KEY_MAP.get("variant")).toEqual(queryKeys.variants);
		});

		it("maps cover-letter to coverLetters query key", () => {
			expect(RESOURCE_QUERY_KEY_MAP.get(RESOURCE_COVER_LETTER)).toEqual(
				queryKeys.coverLetters,
			);
		});

		it("maps change-flag to changeFlags query key", () => {
			expect(RESOURCE_QUERY_KEY_MAP.get(RESOURCE_CHANGE_FLAG)).toEqual(
				queryKeys.changeFlags,
			);
		});

		it("maps embedding to jobs query key", () => {
			expect(RESOURCE_QUERY_KEY_MAP.get(RESOURCE_EMBEDDING)).toEqual(
				queryKeys.jobs,
			);
		});

		it("returns undefined for unknown keys", () => {
			expect(RESOURCE_QUERY_KEY_MAP.get("unknown")).toBeUndefined();
		});
	});

	// -----------------------------------------------------------------------
	// handleDataChanged
	// -----------------------------------------------------------------------

	describe("handleDataChanged", () => {
		it("invalidates the list query key for a known resource", () => {
			handleDataChanged(
				queryClient,
				RESOURCE_JOB_POSTING,
				TEST_ID,
				ACTION_UPDATED,
			);

			expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
				queryKey: queryKeys.jobs,
			});
		});

		it("invalidates on created action", () => {
			handleDataChanged(queryClient, "application", TEST_ID, ACTION_CREATED);

			expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
				queryKey: queryKeys.applications,
			});
		});

		it("invalidates on deleted action", () => {
			handleDataChanged(queryClient, "persona", TEST_ID, ACTION_DELETED);

			expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
				queryKey: queryKeys.personas,
			});
		});

		it("invalidates resume queries", () => {
			handleDataChanged(queryClient, "resume", TEST_ID, ACTION_UPDATED);

			expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
				queryKey: queryKeys.resumes,
			});
		});

		it("invalidates variant queries", () => {
			handleDataChanged(queryClient, "variant", TEST_ID, ACTION_CREATED);

			expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
				queryKey: queryKeys.variants,
			});
		});

		it("invalidates cover-letter queries", () => {
			handleDataChanged(
				queryClient,
				RESOURCE_COVER_LETTER,
				TEST_ID,
				ACTION_UPDATED,
			);

			expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
				queryKey: queryKeys.coverLetters,
			});
		});

		it("invalidates change-flag queries", () => {
			handleDataChanged(
				queryClient,
				RESOURCE_CHANGE_FLAG,
				TEST_ID,
				ACTION_UPDATED,
			);

			expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
				queryKey: queryKeys.changeFlags,
			});
		});

		it("invalidates job queries for embedding resource", () => {
			handleDataChanged(
				queryClient,
				RESOURCE_EMBEDDING,
				TEST_ID,
				ACTION_UPDATED,
			);

			expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
				queryKey: queryKeys.jobs,
			});
		});

		it("does not call invalidateQueries for unknown resources", () => {
			handleDataChanged(
				queryClient,
				"unknown-resource",
				TEST_ID,
				ACTION_UPDATED,
			);

			expect(queryClient.invalidateQueries).not.toHaveBeenCalled();
		});

		it("does not call invalidateQueries for empty resource name", () => {
			handleDataChanged(queryClient, "", TEST_ID, ACTION_UPDATED);

			expect(queryClient.invalidateQueries).not.toHaveBeenCalled();
		});

		it("calls invalidateQueries exactly once per event", () => {
			handleDataChanged(
				queryClient,
				RESOURCE_JOB_POSTING,
				TEST_ID,
				ACTION_UPDATED,
			);

			expect(queryClient.invalidateQueries).toHaveBeenCalledTimes(1);
		});

		it("ignores __proto__ resource name (prototype pollution)", () => {
			handleDataChanged(queryClient, "__proto__", TEST_ID, ACTION_UPDATED);

			expect(queryClient.invalidateQueries).not.toHaveBeenCalled();
		});

		it("ignores constructor resource name (prototype pollution)", () => {
			handleDataChanged(queryClient, "constructor", TEST_ID, ACTION_UPDATED);

			expect(queryClient.invalidateQueries).not.toHaveBeenCalled();
		});

		it("ignores toString resource name (prototype pollution)", () => {
			handleDataChanged(queryClient, "toString", TEST_ID, ACTION_UPDATED);

			expect(queryClient.invalidateQueries).not.toHaveBeenCalled();
		});
	});

	// -----------------------------------------------------------------------
	// handleReconnect
	// -----------------------------------------------------------------------

	describe("handleReconnect", () => {
		it("invalidates all queries with no filter", () => {
			handleReconnect(queryClient);

			expect(queryClient.invalidateQueries).toHaveBeenCalledWith();
		});

		it("calls invalidateQueries exactly once", () => {
			handleReconnect(queryClient);

			expect(queryClient.invalidateQueries).toHaveBeenCalledTimes(1);
		});
	});

	// -----------------------------------------------------------------------
	// createSSEQueryBridge
	// -----------------------------------------------------------------------

	describe("createSSEQueryBridge", () => {
		it("returns onDataChanged and onReconnect callbacks", () => {
			const bridge = createSSEQueryBridge(queryClient);

			expect(bridge).toHaveProperty("onDataChanged");
			expect(bridge).toHaveProperty("onReconnect");
			expect(typeof bridge.onDataChanged).toBe("function");
			expect(typeof bridge.onReconnect).toBe("function");
		});

		it("onDataChanged delegates to handleDataChanged", () => {
			const bridge = createSSEQueryBridge(queryClient);

			bridge.onDataChanged(RESOURCE_JOB_POSTING, TEST_ID, ACTION_UPDATED);

			expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
				queryKey: queryKeys.jobs,
			});
		});

		it("onReconnect delegates to handleReconnect", () => {
			const bridge = createSSEQueryBridge(queryClient);

			bridge.onReconnect();

			expect(queryClient.invalidateQueries).toHaveBeenCalledWith();
		});

		it("onDataChanged ignores unknown resources", () => {
			const bridge = createSSEQueryBridge(queryClient);

			bridge.onDataChanged("not-a-resource", TEST_ID, ACTION_UPDATED);

			expect(queryClient.invalidateQueries).not.toHaveBeenCalled();
		});

		it("calls onEmbeddingUpdated when embedding resource changes", () => {
			const onEmbeddingUpdated = vi.fn();
			const bridge = createSSEQueryBridge(queryClient, {
				onEmbeddingUpdated,
			});

			bridge.onDataChanged(RESOURCE_EMBEDDING, TEST_ID, ACTION_UPDATED);

			expect(onEmbeddingUpdated).toHaveBeenCalledTimes(1);
		});

		it("does not call onEmbeddingUpdated for non-embedding resources", () => {
			const onEmbeddingUpdated = vi.fn();
			const bridge = createSSEQueryBridge(queryClient, {
				onEmbeddingUpdated,
			});

			bridge.onDataChanged(RESOURCE_JOB_POSTING, TEST_ID, ACTION_UPDATED);

			expect(onEmbeddingUpdated).not.toHaveBeenCalled();
		});

		it("works without onEmbeddingUpdated option for embedding resource", () => {
			const bridge = createSSEQueryBridge(queryClient);

			bridge.onDataChanged(RESOURCE_EMBEDDING, TEST_ID, ACTION_UPDATED);

			expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
				queryKey: queryKeys.jobs,
			});
		});
	});
});
