/**
 * Tests for the register page component.
 *
 * REQ-013 §8.3: Full-screen register page with email/password/confirm form,
 * OAuth buttons (Google, LinkedIn), password strength indicator,
 * and post-registration email confirmation flow.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RegisterPage from "./page";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_API_URL = "http://localhost:8000/api/v1";
const TEST_EMAIL = "jane@example.com";
const TEST_PASSWORD = "P@ssw0rd!";
const REGISTER_SUBMIT_TESTID = "register-submit";

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

function renderRegister() {
	const user = userEvent.setup();
	render(<RegisterPage />);
	return user;
}

async function fillAndSubmitRegistration(
	user: ReturnType<typeof userEvent.setup>,
	email = TEST_EMAIL,
	password = TEST_PASSWORD,
	confirmPassword = TEST_PASSWORD,
) {
	await user.type(screen.getByLabelText(/^email$/i), email);
	await user.type(screen.getByLabelText(/^password$/i), password);
	await user.type(screen.getByLabelText(/confirm password/i), confirmPassword);
	await user.click(screen.getByTestId(REGISTER_SUBMIT_TESTID));
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

describe("RegisterPage", () => {
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
			renderRegister();

			expect(screen.getByText(/create your account/i)).toBeInTheDocument();
		});

		it("renders Google OAuth button with correct href", () => {
			renderRegister();

			const googleLink = screen.getByTestId("oauth-google");
			expect(googleLink).toBeInTheDocument();
			expect(googleLink).toHaveAttribute(
				"href",
				`${DEFAULT_API_URL}/auth/providers/google`,
			);
		});

		it("renders LinkedIn OAuth button with correct href", () => {
			renderRegister();

			const linkedinLink = screen.getByTestId("oauth-linkedin");
			expect(linkedinLink).toBeInTheDocument();
			expect(linkedinLink).toHaveAttribute(
				"href",
				`${DEFAULT_API_URL}/auth/providers/linkedin`,
			);
		});

		it("renders email, password, and confirm password inputs", () => {
			renderRegister();

			expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
		});

		it("renders Create Account submit button", () => {
			renderRegister();

			const btn = screen.getByTestId(REGISTER_SUBMIT_TESTID);
			expect(btn).toBeInTheDocument();
			expect(btn).toHaveTextContent(/create account/i);
		});

		it("renders Sign In link to /login", () => {
			renderRegister();

			const link = screen.getByRole("link", { name: /sign in/i });
			expect(link).toBeInTheDocument();
			expect(link).toHaveAttribute("href", "/login");
		});

		it("renders or-divider between OAuth and form", () => {
			renderRegister();

			expect(screen.getByText(/or sign up with/i)).toBeInTheDocument();
		});

		it("sets autocomplete on email input", () => {
			renderRegister();

			expect(screen.getByLabelText(/^email$/i)).toHaveAttribute(
				"autocomplete",
				"email",
			);
		});

		it("sets autocomplete on password input", () => {
			renderRegister();

			expect(screen.getByLabelText(/^password$/i)).toHaveAttribute(
				"autocomplete",
				"new-password",
			);
		});

		it("sets autocomplete on confirm password input", () => {
			renderRegister();

			expect(screen.getByLabelText(/confirm password/i)).toHaveAttribute(
				"autocomplete",
				"new-password",
			);
		});
	});

	// -----------------------------------------------------------------------
	// Password strength indicator
	// -----------------------------------------------------------------------

	describe("password strength indicator", () => {
		it("shows all requirements unchecked initially", () => {
			renderRegister();

			expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
			expect(screen.getByText(/at least one letter/i)).toBeInTheDocument();
			expect(screen.getByText(/at least one number/i)).toBeInTheDocument();
			expect(
				screen.getByText(/at least one special character/i),
			).toBeInTheDocument();
		});

		it("checks length requirement when password has 8+ chars", async () => {
			const user = renderRegister();

			await user.type(screen.getByLabelText(/^password$/i), "abcdefgh");

			const lengthReq = screen.getByTestId("req-length");
			expect(lengthReq).toHaveAttribute("data-met", "true");
		});

		it("checks letter requirement when password has a letter", async () => {
			const user = renderRegister();

			await user.type(screen.getByLabelText(/^password$/i), "a");

			const letterReq = screen.getByTestId("req-letter");
			expect(letterReq).toHaveAttribute("data-met", "true");
		});

		it("checks number requirement when password has a digit", async () => {
			const user = renderRegister();

			await user.type(screen.getByLabelText(/^password$/i), "abc1");

			const numberReq = screen.getByTestId("req-number");
			expect(numberReq).toHaveAttribute("data-met", "true");
		});

		it("checks special char requirement when password has special", async () => {
			const user = renderRegister();

			await user.type(screen.getByLabelText(/^password$/i), "abc!");

			const specialReq = screen.getByTestId("req-special");
			expect(specialReq).toHaveAttribute("data-met", "true");
		});

		it("marks requirements unmet when password is weak", async () => {
			const user = renderRegister();

			await user.type(screen.getByLabelText(/^password$/i), "123");

			const lengthReq = screen.getByTestId("req-length");
			const letterReq = screen.getByTestId("req-letter");
			const numberReq = screen.getByTestId("req-number");
			const specialReq = screen.getByTestId("req-special");
			expect(lengthReq).toHaveAttribute("data-met", "false");
			expect(letterReq).toHaveAttribute("data-met", "false");
			expect(numberReq).toHaveAttribute("data-met", "true");
			expect(specialReq).toHaveAttribute("data-met", "false");
		});
	});

	// -----------------------------------------------------------------------
	// Form validation
	// -----------------------------------------------------------------------

	describe("form validation", () => {
		it("shows error when email is empty on submit", async () => {
			const user = renderRegister();

			await user.type(screen.getByLabelText(/^password$/i), TEST_PASSWORD);
			await user.type(
				screen.getByLabelText(/confirm password/i),
				TEST_PASSWORD,
			);
			await user.click(screen.getByTestId(REGISTER_SUBMIT_TESTID));

			await waitFor(() => {
				expect(screen.getByText(/email is required/i)).toBeInTheDocument();
			});
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});

		it("shows error for invalid email format", async () => {
			const user = renderRegister();

			await user.type(screen.getByLabelText(/^email$/i), "not-an-email");
			await user.type(screen.getByLabelText(/^password$/i), TEST_PASSWORD);
			await user.type(
				screen.getByLabelText(/confirm password/i),
				TEST_PASSWORD,
			);
			await user.click(screen.getByTestId(REGISTER_SUBMIT_TESTID));

			await waitFor(() => {
				expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
			});
		});

		it("shows error when password is empty on submit", async () => {
			const user = renderRegister();

			await user.type(screen.getByLabelText(/^email$/i), TEST_EMAIL);
			await user.click(screen.getByTestId(REGISTER_SUBMIT_TESTID));

			await waitFor(() => {
				expect(screen.getByText(/password is required/i)).toBeInTheDocument();
			});
		});

		it("shows error when passwords do not match", async () => {
			const user = renderRegister();

			await user.type(screen.getByLabelText(/^email$/i), TEST_EMAIL);
			await user.type(screen.getByLabelText(/^password$/i), TEST_PASSWORD);
			await user.type(
				screen.getByLabelText(/confirm password/i),
				"DifferentPass1!",
			);
			await user.click(screen.getByTestId(REGISTER_SUBMIT_TESTID));

			await waitFor(() => {
				expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Form submission
	// -----------------------------------------------------------------------

	describe("form submission", () => {
		it("calls register API with email and password", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({
				data: { id: "u-1", email: TEST_EMAIL },
			});
			const user = renderRegister();

			await fillAndSubmitRegistration(user);

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith("/auth/register", {
					email: TEST_EMAIL,
					password: TEST_PASSWORD,
				});
			});
		});

		it("shows submitting state during API call", async () => {
			mocks.mockApiPost.mockReturnValue(new Promise(() => {}));
			const user = renderRegister();

			await fillAndSubmitRegistration(user);

			await waitFor(() => {
				const btn = screen.getByTestId(REGISTER_SUBMIT_TESTID);
				expect(btn).toBeDisabled();
			});
		});

		it("shows email confirmation after successful registration", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({
				data: { id: "u-1", email: TEST_EMAIL },
			});
			const user = renderRegister();

			await fillAndSubmitRegistration(user);

			await waitFor(() => {
				expect(screen.getByText(/check your email/i)).toBeInTheDocument();
			});
		});

		it("shows error for duplicate email (409)", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError(
					"EMAIL_ALREADY_EXISTS",
					"Email already registered",
					409,
				),
			);
			const user = renderRegister();

			await fillAndSubmitRegistration(user);

			await waitFor(() => {
				expect(
					screen.getByText(/email already registered/i),
				).toBeInTheDocument();
			});
		});

		it("shows error for breached password (422)", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError(
					"PASSWORD_BREACHED",
					"This password has appeared in a data breach",
					422,
				),
			);
			const user = renderRegister();

			await fillAndSubmitRegistration(user);

			await waitFor(() => {
				expect(
					screen.getByText(/data breach.*choose a different one/i),
				).toBeInTheDocument();
			});
		});

		it("shows client-side error for weak password (400)", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError(
					"VALIDATION_ERROR",
					"Password must contain at least one special character",
					400,
				),
			);
			const user = renderRegister();

			await fillAndSubmitRegistration(user);

			await waitFor(() => {
				expect(
					screen.getByText(/does not meet requirements/i),
				).toBeInTheDocument();
			});
		});

		it("shows error for rate limiting (429)", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError("RATE_LIMITED", "Too many attempts", 429),
			);
			const user = renderRegister();

			await fillAndSubmitRegistration(user);

			await waitFor(() => {
				expect(screen.getByText(/too many attempts/i)).toBeInTheDocument();
			});
		});

		it("shows generic error for network failures", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(new Error("Network failure"));
			const user = renderRegister();

			await fillAndSubmitRegistration(user);

			await waitFor(() => {
				expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
			});
		});

		it("re-enables submit button after error", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(new Error("fail"));
			const user = renderRegister();

			await fillAndSubmitRegistration(user);

			await waitFor(() => {
				const btn = screen.getByTestId(REGISTER_SUBMIT_TESTID);
				expect(btn).not.toBeDisabled();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Email confirmation view
	// -----------------------------------------------------------------------

	describe("email confirmation", () => {
		it("shows Back to sign in link from confirmation", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({
				data: { id: "u-1", email: TEST_EMAIL },
			});
			const user = renderRegister();

			await fillAndSubmitRegistration(user);

			await waitFor(() => {
				expect(
					screen.getByRole("link", { name: /sign in/i }),
				).toBeInTheDocument();
			});
		});

		it("hides registration form after success", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({
				data: { id: "u-1", email: TEST_EMAIL },
			});
			const user = renderRegister();

			await fillAndSubmitRegistration(user);

			await waitFor(() => {
				expect(screen.getByText(/check your email/i)).toBeInTheDocument();
			});
			expect(screen.queryByLabelText(/^password$/i)).not.toBeInTheDocument();
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
				},
				status: "authenticated",
			});

			renderRegister();

			expect(mocks.mockRouterReplace).toHaveBeenCalledWith("/");
		});

		it("does not redirect when loading", () => {
			mocks.mockUseSession.mockReturnValue({
				session: null,
				status: "loading",
			});

			renderRegister();

			expect(mocks.mockRouterReplace).not.toHaveBeenCalled();
		});

		it("does not redirect when unauthenticated", () => {
			renderRegister();

			expect(mocks.mockRouterReplace).not.toHaveBeenCalled();
		});
	});
});
