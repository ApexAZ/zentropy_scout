/**
 * Tests for embedding staleness notification utilities.
 *
 * REQ-012 §7.7: After persona edits that affect matching, show
 * "Updating your match profile..." indicator. On completion (SSE
 * data_changed for embeddings), show "Match profile updated."
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockWarning: vi.fn(),
	mockInfo: vi.fn(),
}));

vi.mock("./toast", () => ({
	showToast: {
		warning: mocks.mockWarning,
		info: mocks.mockInfo,
	},
}));

import {
	notifyEmbeddingComplete,
	notifyEmbeddingUpdate,
} from "./embedding-staleness";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
});

describe("notifyEmbeddingUpdate", () => {
	it("shows warning toast with match profile updating message", () => {
		notifyEmbeddingUpdate();

		expect(mocks.mockWarning).toHaveBeenCalledWith(
			"Updating your match profile...",
		);
	});

	it("calls warning toast exactly once", () => {
		notifyEmbeddingUpdate();

		expect(mocks.mockWarning).toHaveBeenCalledTimes(1);
	});

	it("does not show info toast", () => {
		notifyEmbeddingUpdate();

		expect(mocks.mockInfo).not.toHaveBeenCalled();
	});
});

describe("notifyEmbeddingComplete", () => {
	it("shows info toast with match profile updated message", () => {
		notifyEmbeddingComplete();

		expect(mocks.mockInfo).toHaveBeenCalledWith(
			"Match profile updated. Job scores may have changed.",
		);
	});

	it("calls info toast exactly once", () => {
		notifyEmbeddingComplete();

		expect(mocks.mockInfo).toHaveBeenCalledTimes(1);
	});

	it("does not show warning toast", () => {
		notifyEmbeddingComplete();

		expect(mocks.mockWarning).not.toHaveBeenCalled();
	});
});
