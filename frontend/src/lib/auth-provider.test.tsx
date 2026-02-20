/**
 * Tests for AuthProvider session management.
 *
 * REQ-013 §8.4–§8.6: AuthProvider fetches /auth/me on mount,
 * provides session state via useSession() hook, redirects to
 * /login on 401.
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
	mockApiGet: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
}));

import { AuthProvider, useSession } from "./auth-provider";

// ---------------------------------------------------------------------------
// Test constants
// ---------------------------------------------------------------------------

/** Raw backend response shape (snake_case). */
const TEST_USER_RESPONSE = {
	id: "00000000-0000-4000-a000-000000000001",
	email: "test@example.com",
	name: "Test User",
	image: null,
	email_verified: true,
	has_password: false,
};

/** Expected mapped session shape (camelCase). */
const TEST_USER_SESSION = {
	id: "00000000-0000-4000-a000-000000000001",
	email: "test@example.com",
	name: "Test User",
	image: null,
	emailVerified: true,
	hasPassword: false,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function wrapper({ children }: { children: ReactNode }) {
	return <AuthProvider>{children}</AuthProvider>;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AuthProvider", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("renders children", () => {
		mocks.mockApiGet.mockResolvedValue({ data: TEST_USER_RESPONSE });

		render(
			<AuthProvider>
				<p>hello</p>
			</AuthProvider>,
		);

		expect(screen.getByText("hello")).toBeInTheDocument();
	});

	it("starts in loading state", () => {
		// Never resolve — keep in loading state
		mocks.mockApiGet.mockReturnValue(new Promise(() => {}));

		const { result } = renderHook(() => useSession(), { wrapper });

		expect(result.current.status).toBe("loading");
		expect(result.current.session).toBeNull();
	});

	it("transitions to authenticated on successful /auth/me", async () => {
		mocks.mockApiGet.mockResolvedValue({ data: TEST_USER_RESPONSE });

		const { result } = renderHook(() => useSession(), { wrapper });

		await waitFor(() => {
			expect(result.current.status).toBe("authenticated");
		});

		expect(result.current.session).toEqual(TEST_USER_SESSION);
	});

	it("transitions to unauthenticated on 401 from /auth/me", async () => {
		const error = Object.assign(new Error("Not authenticated"), {
			code: "UNAUTHORIZED",
			status: 401,
		});
		mocks.mockApiGet.mockRejectedValue(error);

		const { result } = renderHook(() => useSession(), { wrapper });

		await waitFor(() => {
			expect(result.current.status).toBe("unauthenticated");
		});

		expect(result.current.session).toBeNull();
	});

	it("transitions to unauthenticated on network error", async () => {
		mocks.mockApiGet.mockRejectedValue(new Error("Network error"));

		const { result } = renderHook(() => useSession(), { wrapper });

		await waitFor(() => {
			expect(result.current.status).toBe("unauthenticated");
		});

		expect(result.current.session).toBeNull();
	});

	it("calls /auth/me endpoint on mount", async () => {
		mocks.mockApiGet.mockResolvedValue({ data: TEST_USER_RESPONSE });

		renderHook(() => useSession(), { wrapper });

		await waitFor(() => {
			expect(mocks.mockApiGet).toHaveBeenCalledWith("/auth/me");
		});
	});

	it("revalidates session on visibility change", async () => {
		mocks.mockApiGet.mockResolvedValue({ data: TEST_USER_RESPONSE });

		const { result } = renderHook(() => useSession(), { wrapper });

		await waitFor(() => {
			expect(result.current.status).toBe("authenticated");
		});

		// Simulate tab becoming hidden then visible again
		mocks.mockApiGet.mockRejectedValue(new Error("Session expired"));

		await act(async () => {
			Object.defineProperty(document, "visibilityState", {
				value: "visible",
				writable: true,
			});
			document.dispatchEvent(new Event("visibilitychange"));
		});

		await waitFor(() => {
			expect(result.current.status).toBe("unauthenticated");
		});
	});

	it("throws when useSession is used outside AuthProvider", () => {
		// Suppress console.error from React error boundary
		const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

		expect(() => {
			renderHook(() => useSession());
		}).toThrow("useSession must be used within an AuthProvider");

		consoleSpy.mockRestore();
	});
});
