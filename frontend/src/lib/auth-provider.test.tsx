/**
 * Tests for AuthProvider session management.
 *
 * REQ-013 §8.4–§8.6: AuthProvider fetches /auth/me on mount,
 * provides session state via useSession() hook, redirects to
 * /login on 401.
 * REQ-013 §8.9: logout() and logoutAllDevices() clear cache,
 * context, and redirect.
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
	mockApiPost: vi.fn(),
	mockQueryClientClear: vi.fn(),
	mockLocationHref: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
	apiGet: mocks.mockApiGet,
	apiPost: mocks.mockApiPost,
}));

vi.mock("@/lib/query-client", () => ({
	getActiveQueryClient: () => ({ clear: mocks.mockQueryClientClear }),
	setActiveQueryClient: vi.fn(),
	createQueryClient: vi.fn(),
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
	canResetPassword: false,
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
	const originalLocation = globalThis.location;

	beforeEach(() => {
		vi.clearAllMocks();

		// Mock location.href setter to capture redirects
		Object.defineProperty(globalThis, "location", {
			value: {
				...originalLocation,
				get href() {
					return originalLocation.href;
				},
				set href(url: string) {
					mocks.mockLocationHref(url);
				},
			},
			writable: true,
			configurable: true,
		});
	});

	afterEach(() => {
		vi.restoreAllMocks();
		// Restore original location
		Object.defineProperty(globalThis, "location", {
			value: originalLocation,
			writable: true,
			configurable: true,
		});
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

	// -------------------------------------------------------------------
	// Logout (REQ-013 §8.9)
	// -------------------------------------------------------------------

	/** Render an authenticated hook, ready for logout/logoutAllDevices calls. */
	async function setupAuthenticated() {
		mocks.mockApiGet.mockResolvedValue({ data: TEST_USER_RESPONSE });
		const hook = renderHook(() => useSession(), { wrapper });
		await waitFor(() =>
			expect(hook.result.current.status).toBe("authenticated"),
		);
		return hook;
	}

	describe("logout", () => {
		it("calls POST /auth/logout", async () => {
			mocks.mockApiPost.mockResolvedValue({ data: { message: "ok" } });
			const { result } = await setupAuthenticated();

			await act(async () => {
				await result.current.logout();
			});

			expect(mocks.mockApiPost).toHaveBeenCalledWith("/auth/logout");
		});

		it("clears TanStack Query cache", async () => {
			mocks.mockApiPost.mockResolvedValue({ data: { message: "ok" } });
			const { result } = await setupAuthenticated();

			await act(async () => {
				await result.current.logout();
			});

			expect(mocks.mockQueryClientClear).toHaveBeenCalled();
		});

		it("clears session state to unauthenticated", async () => {
			mocks.mockApiPost.mockResolvedValue({ data: { message: "ok" } });
			const { result } = await setupAuthenticated();

			await act(async () => {
				await result.current.logout();
			});

			expect(result.current.session).toBeNull();
			expect(result.current.status).toBe("unauthenticated");
		});

		it("redirects to /login", async () => {
			mocks.mockApiPost.mockResolvedValue({ data: { message: "ok" } });
			const { result } = await setupAuthenticated();

			await act(async () => {
				await result.current.logout();
			});

			expect(mocks.mockLocationHref).toHaveBeenCalledWith("/login");
		});

		it("redirects even if API call fails", async () => {
			mocks.mockApiPost.mockRejectedValue(new Error("Network error"));
			const { result } = await setupAuthenticated();

			await act(async () => {
				await result.current.logout();
			});

			expect(mocks.mockLocationHref).toHaveBeenCalledWith("/login");
		});
	});

	// -------------------------------------------------------------------
	// Logout all devices (REQ-013 §8.9)
	// -------------------------------------------------------------------

	describe("logoutAllDevices", () => {
		it("calls POST /auth/invalidate-sessions then POST /auth/logout", async () => {
			mocks.mockApiPost
				.mockResolvedValueOnce({ data: { message: "invalidated" } })
				.mockResolvedValueOnce({ data: { message: "ok" } });
			const { result } = await setupAuthenticated();

			await act(async () => {
				await result.current.logoutAllDevices();
			});

			expect(mocks.mockApiPost).toHaveBeenCalledWith(
				"/auth/invalidate-sessions",
			);
			expect(mocks.mockApiPost).toHaveBeenCalledWith("/auth/logout");
		});

		it("clears TanStack Query cache", async () => {
			mocks.mockApiPost.mockResolvedValue({ data: { message: "ok" } });
			const { result } = await setupAuthenticated();

			await act(async () => {
				await result.current.logoutAllDevices();
			});

			expect(mocks.mockQueryClientClear).toHaveBeenCalled();
		});

		it("clears session state to unauthenticated", async () => {
			mocks.mockApiPost.mockResolvedValue({ data: { message: "ok" } });
			const { result } = await setupAuthenticated();

			await act(async () => {
				await result.current.logoutAllDevices();
			});

			expect(result.current.session).toBeNull();
			expect(result.current.status).toBe("unauthenticated");
		});

		it("redirects to /login", async () => {
			mocks.mockApiPost.mockResolvedValue({ data: { message: "ok" } });
			const { result } = await setupAuthenticated();

			await act(async () => {
				await result.current.logoutAllDevices();
			});

			expect(mocks.mockLocationHref).toHaveBeenCalledWith("/login");
		});

		it("still logs out locally if invalidate-sessions fails", async () => {
			mocks.mockApiPost
				.mockRejectedValueOnce(new Error("Network error"))
				.mockResolvedValueOnce({ data: { message: "ok" } });
			const { result } = await setupAuthenticated();

			await act(async () => {
				await result.current.logoutAllDevices();
			});

			expect(mocks.mockLocationHref).toHaveBeenCalledWith("/login");
		});
	});
});
