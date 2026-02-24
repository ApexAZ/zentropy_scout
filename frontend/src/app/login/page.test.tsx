/**
 * Tests for the login page component.
 *
 * REQ-013 §8.2: Full-screen login page with email/password form,
 * OAuth buttons (Google, LinkedIn), forgot password (magic link),
 * and post-auth redirect logic.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "./page";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_API_URL = "http://localhost:8000/api/v1";
const TEST_EMAIL = "jane@example.com";
const TEST_PASSWORD = "P@ssw0rd!";
const LOGIN_SUBMIT_TESTID = "login-submit";
const MAGIC_LINK_SUBMIT_TESTID = "magic-link-submit";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	class MockApiError extends Error {
		code: string;
		status: number;
		constructor(code: string, message: string, status: number) {
			super(message);
			this.name = "ApiError";
			this.code = code;
			this.status = status;
		}
	}
	return {
		mockApiPost: vi.fn(),
		mockBuildUrl: vi.fn((path: string) => `${DEFAULT_API_URL}${path}`),
		MockApiError,
		mockRouterReplace: vi.fn(),
		mockUseSession: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiPost: mocks.mockApiPost,
	buildUrl: mocks.mockBuildUrl,
	ApiError: mocks.MockApiError,
}));

vi.mock("next/navigation", () => ({
	useRouter: () => ({
		replace: mocks.mockRouterReplace,
	}),
}));

vi.mock("@/lib/auth-provider", () => ({
	useSession: mocks.mockUseSession,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderLogin() {
	const user = userEvent.setup();
	render(<LoginPage />);
	return user;
}

async function fillAndSubmitCredentials(
	user: ReturnType<typeof userEvent.setup>,
	email = TEST_EMAIL,
	password = TEST_PASSWORD,
) {
	await user.type(screen.getByLabelText(/email/i), email);
	await user.type(screen.getByLabelText(/password/i), password);
	await user.click(screen.getByTestId(LOGIN_SUBMIT_TESTID));
}

function clickForgotPassword(user: ReturnType<typeof userEvent.setup>) {
	return user.click(screen.getByRole("button", { name: /forgot password/i }));
}

async function submitMagicLink(
	user: ReturnType<typeof userEvent.setup>,
	email = TEST_EMAIL,
) {
	await clickForgotPassword(user);
	await user.type(screen.getByLabelText(/email/i), email);
	await user.click(screen.getByTestId(MAGIC_LINK_SUBMIT_TESTID));
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

describe("LoginPage", () => {
	beforeEach(() => {
		mocks.mockApiPost.mockReset();
		mocks.mockRouterReplace.mockReset();
		mocks.mockUseSession.mockReset();

		// Default: unauthenticated
		mocks.mockUseSession.mockReturnValue({
			session: null,
			status: "unauthenticated",
		});
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("renders the page heading", () => {
			renderLogin();

			expect(
				screen.getByText(/sign in to zentropy scout/i),
			).toBeInTheDocument();
		});

		it("renders Google OAuth button with correct href", () => {
			renderLogin();

			const googleLink = screen.getByTestId("oauth-google");
			expect(googleLink).toBeInTheDocument();
			expect(googleLink).toHaveAttribute(
				"href",
				`${DEFAULT_API_URL}/auth/providers/google`,
			);
		});

		it("renders LinkedIn OAuth button with correct href", () => {
			renderLogin();

			const linkedinLink = screen.getByTestId("oauth-linkedin");
			expect(linkedinLink).toBeInTheDocument();
			expect(linkedinLink).toHaveAttribute(
				"href",
				`${DEFAULT_API_URL}/auth/providers/linkedin`,
			);
		});

		it("renders email and password inputs", () => {
			renderLogin();

			expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
		});

		it("renders Sign In submit button", () => {
			renderLogin();

			const btn = screen.getByTestId(LOGIN_SUBMIT_TESTID);
			expect(btn).toBeInTheDocument();
			expect(btn).toHaveTextContent(/sign in/i);
		});

		it("renders Forgot password link", () => {
			renderLogin();

			expect(
				screen.getByRole("button", { name: /forgot password/i }),
			).toBeInTheDocument();
		});

		it("renders Create account link to /register", () => {
			renderLogin();

			const link = screen.getByRole("link", { name: /create account/i });
			expect(link).toBeInTheDocument();
			expect(link).toHaveAttribute("href", "/register");
		});

		it("renders or-divider between OAuth and form", () => {
			renderLogin();

			expect(screen.getByText(/or sign in with/i)).toBeInTheDocument();
		});

		it("sets autocomplete on email input", () => {
			renderLogin();

			expect(screen.getByLabelText(/email/i)).toHaveAttribute(
				"autocomplete",
				"email",
			);
		});

		it("sets autocomplete on password input", () => {
			renderLogin();

			expect(screen.getByLabelText(/password/i)).toHaveAttribute(
				"autocomplete",
				"current-password",
			);
		});
	});

	// -----------------------------------------------------------------------
	// Form validation
	// -----------------------------------------------------------------------

	describe("form validation", () => {
		it("shows error when email is empty on submit", async () => {
			const user = renderLogin();

			await user.type(screen.getByLabelText(/password/i), "somepass");
			await user.click(screen.getByTestId(LOGIN_SUBMIT_TESTID));

			await waitFor(() => {
				expect(screen.getByText(/email is required/i)).toBeInTheDocument();
			});
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});

		it("shows error for invalid email format", async () => {
			const user = renderLogin();

			await user.type(screen.getByLabelText(/email/i), "not-an-email");
			await user.type(screen.getByLabelText(/password/i), "somepass");
			await user.click(screen.getByTestId(LOGIN_SUBMIT_TESTID));

			await waitFor(() => {
				expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
			});
		});

		it("shows error when password is empty on submit", async () => {
			const user = renderLogin();

			await user.type(screen.getByLabelText(/email/i), TEST_EMAIL);
			await user.click(screen.getByTestId(LOGIN_SUBMIT_TESTID));

			await waitFor(() => {
				expect(screen.getByText(/password is required/i)).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Form submission
	// -----------------------------------------------------------------------

	describe("form submission", () => {
		it("calls verify-password API with email and password", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({ data: {} });
			const user = renderLogin();

			await fillAndSubmitCredentials(user);

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					"/auth/verify-password",
					{ email: TEST_EMAIL, password: TEST_PASSWORD },
				);
			});
		});

		it("shows submitting state during API call", async () => {
			mocks.mockApiPost.mockReturnValue(new Promise(() => {}));
			const user = renderLogin();

			await fillAndSubmitCredentials(user);

			await waitFor(() => {
				const btn = screen.getByTestId(LOGIN_SUBMIT_TESTID);
				expect(btn).toBeDisabled();
			});
		});

		it("redirects to / after successful login", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({ data: {} });
			const user = renderLogin();

			await fillAndSubmitCredentials(user);

			await waitFor(() => {
				// Full page load (not client-side nav) so AuthProvider remounts
				expect(globalThis.location.pathname).toBe("/");
			});
		});

		it("shows error for invalid credentials (401)", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError(
					"INVALID_CREDENTIALS",
					"Invalid email or password",
					401,
				),
			);
			const user = renderLogin();

			await fillAndSubmitCredentials(user);

			await waitFor(() => {
				expect(
					screen.getByText(/invalid email or password/i),
				).toBeInTheDocument();
			});
		});

		it("shows error for rate limiting (429)", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError("RATE_LIMITED", "Too many attempts", 429),
			);
			const user = renderLogin();

			await fillAndSubmitCredentials(user);

			await waitFor(() => {
				expect(screen.getByText(/too many attempts/i)).toBeInTheDocument();
			});
		});

		it("shows generic error for network failures", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(new Error("Network failure"));
			const user = renderLogin();

			await fillAndSubmitCredentials(user);

			await waitFor(() => {
				expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
			});
		});

		it("re-enables submit button after error", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(new Error("fail"));
			const user = renderLogin();

			await fillAndSubmitCredentials(user);

			await waitFor(() => {
				const btn = screen.getByTestId(LOGIN_SUBMIT_TESTID);
				expect(btn).not.toBeDisabled();
			});
		});

		it("clears error when switching to forgot-password view", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(new Error("fail"));
			const user = renderLogin();

			await fillAndSubmitCredentials(user);

			await waitFor(() => {
				expect(screen.getByTestId("submit-error")).toBeInTheDocument();
			});

			await clickForgotPassword(user);

			expect(screen.queryByTestId("submit-error")).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Forgot password (magic link) flow
	// -----------------------------------------------------------------------

	describe("forgot password flow", () => {
		it("shows magic link form when Forgot password is clicked", async () => {
			const user = renderLogin();

			await clickForgotPassword(user);

			expect(screen.getByText(/send a sign-in link/i)).toBeInTheDocument();
			expect(screen.getByTestId(MAGIC_LINK_SUBMIT_TESTID)).toBeInTheDocument();
			// Password field should be hidden
			expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
		});

		it("calls magic-link API with email and password_reset purpose", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({ data: {} });
			const user = renderLogin();

			await submitMagicLink(user);

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith("/auth/magic-link", {
					email: TEST_EMAIL,
					purpose: "password_reset",
				});
			});
		});

		it("shows confirmation after magic link is sent", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({ data: {} });
			const user = renderLogin();

			await submitMagicLink(user);

			await waitFor(() => {
				expect(screen.getByText(/check your email/i)).toBeInTheDocument();
			});
		});

		it("shows Back to sign in link from confirmation", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({ data: {} });
			const user = renderLogin();

			await submitMagicLink(user);

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /back to sign in/i }),
				).toBeInTheDocument();
			});
		});

		it("returns to login form when Back to sign in is clicked", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({ data: {} });
			const user = renderLogin();

			await submitMagicLink(user);

			await waitFor(() => {
				expect(screen.getByText(/check your email/i)).toBeInTheDocument();
			});

			await user.click(
				screen.getByRole("button", { name: /back to sign in/i }),
			);

			// Should be back on login form
			expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
			expect(screen.getByTestId(LOGIN_SUBMIT_TESTID)).toBeInTheDocument();
		});

		it("shows error when magic link request fails", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(new Error("Network error"));
			const user = renderLogin();

			await submitMagicLink(user);

			await waitFor(() => {
				expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
			});
		});

		it("shows Back to sign in link from forgot password form", async () => {
			const user = renderLogin();

			await clickForgotPassword(user);

			expect(
				screen.getByRole("button", { name: /back to sign in/i }),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Auth redirect
	// -----------------------------------------------------------------------

	describe("auth redirect", () => {
		it("redirects to / when already authenticated", () => {
			mocks.mockUseSession.mockReturnValue({
				session: {
					id: "u-1",
					email: TEST_EMAIL,
					name: null,
					image: null,
					emailVerified: true,
					hasPassword: true,
				},
				status: "authenticated",
			});

			renderLogin();

			expect(mocks.mockRouterReplace).toHaveBeenCalledWith("/");
		});

		it("does not redirect when loading", () => {
			mocks.mockUseSession.mockReturnValue({
				session: null,
				status: "loading",
			});

			renderLogin();

			expect(mocks.mockRouterReplace).not.toHaveBeenCalled();
		});

		it("does not redirect when unauthenticated", () => {
			renderLogin();

			expect(mocks.mockRouterReplace).not.toHaveBeenCalled();
		});
	});
});
