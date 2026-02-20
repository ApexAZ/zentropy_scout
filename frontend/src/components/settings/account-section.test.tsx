/**
 * Tests for the AccountSection component.
 *
 * REQ-013 §8.3a: Account settings section with email display,
 * name edit, password change/set, and sign-out buttons.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TEST_EMAIL = "jane@example.com";

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
		mockApiPatch: vi.fn(),
		MockApiError,
		mockUseSession: vi.fn(),
		mockShowToast: {
			success: vi.fn(),
			error: vi.fn(),
		},
		mockLocationHref: vi.fn(),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiPost: mocks.mockApiPost,
	apiPatch: mocks.mockApiPatch,
	ApiError: mocks.MockApiError,
}));

vi.mock("@/lib/auth-provider", () => ({
	useSession: mocks.mockUseSession,
}));

vi.mock("@/lib/toast", () => ({
	showToast: mocks.mockShowToast,
}));

import { AccountSection } from "./account-section";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const VERIFIED_SESSION = {
	session: {
		id: "u-1",
		email: TEST_EMAIL,
		name: "Jane Smith",
		image: null,
		emailVerified: true,
		hasPassword: true,
	},
	status: "authenticated" as const,
};

const OAUTH_ONLY_SESSION = {
	session: {
		id: "u-1",
		email: TEST_EMAIL,
		name: "Jane Smith",
		image: null,
		emailVerified: true,
		hasPassword: false,
	},
	status: "authenticated" as const,
};

const UNVERIFIED_SESSION = {
	session: {
		id: "u-1",
		email: TEST_EMAIL,
		name: "Jane Smith",
		image: null,
		emailVerified: false,
		hasPassword: true,
	},
	status: "authenticated" as const,
};

function renderAccount() {
	const user = userEvent.setup();
	render(<AccountSection />);
	return user;
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

describe("AccountSection", () => {
	const originalLocation = globalThis.location;

	beforeEach(() => {
		mocks.mockApiPost.mockReset();
		mocks.mockApiPatch.mockReset();
		mocks.mockUseSession.mockReset();
		mocks.mockShowToast.success.mockReset();
		mocks.mockShowToast.error.mockReset();
		mocks.mockLocationHref.mockReset();

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

		// Default: verified user with password
		mocks.mockUseSession.mockReturnValue(VERIFIED_SESSION);
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
		// Restore original location
		Object.defineProperty(globalThis, "location", {
			value: originalLocation,
			writable: true,
			configurable: true,
		});
	});

	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	describe("rendering", () => {
		it("renders the section container", () => {
			renderAccount();

			expect(screen.getByTestId("account-section")).toBeInTheDocument();
		});

		it("displays user email", () => {
			renderAccount();

			expect(screen.getByText(TEST_EMAIL)).toBeInTheDocument();
		});

		it("shows Verified badge when email is verified", () => {
			renderAccount();

			expect(screen.getByText(/verified/i)).toBeInTheDocument();
		});

		it("shows Unverified badge when email is not verified", () => {
			mocks.mockUseSession.mockReturnValue(UNVERIFIED_SESSION);
			renderAccount();

			expect(screen.getByText(/unverified/i)).toBeInTheDocument();
		});

		it("displays user name", () => {
			renderAccount();

			expect(screen.getByText("Jane Smith")).toBeInTheDocument();
		});

		it("shows Change password button when user has password", () => {
			renderAccount();

			expect(
				screen.getByRole("button", { name: /change password/i }),
			).toBeInTheDocument();
		});

		it("shows Set a password button when user has no password", () => {
			mocks.mockUseSession.mockReturnValue(OAUTH_ONLY_SESSION);
			renderAccount();

			expect(
				screen.getByRole("button", { name: /set a password/i }),
			).toBeInTheDocument();
		});

		it("renders Sign out button", () => {
			renderAccount();

			expect(
				screen.getByRole("button", { name: /^sign out$/i }),
			).toBeInTheDocument();
		});

		it("renders Sign out all devices button", () => {
			renderAccount();

			expect(
				screen.getByRole("button", { name: /sign out.*all devices/i }),
			).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Name editing
	// -----------------------------------------------------------------------

	describe("name editing", () => {
		it("shows edit button for name", () => {
			renderAccount();

			expect(
				screen.getByRole("button", { name: /edit.*name/i }),
			).toBeInTheDocument();
		});

		it("shows name input when edit is clicked", async () => {
			const user = renderAccount();

			await user.click(screen.getByRole("button", { name: /edit.*name/i }));

			expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
		});

		it("pre-fills name input with current name", async () => {
			const user = renderAccount();

			await user.click(screen.getByRole("button", { name: /edit.*name/i }));

			expect(screen.getByLabelText(/name/i)).toHaveValue("Jane Smith");
		});

		it("calls API with updated name on save", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: { ...VERIFIED_SESSION.session, name: "Jane Doe" },
			});
			const user = renderAccount();

			await user.click(screen.getByRole("button", { name: /edit.*name/i }));
			const input = screen.getByLabelText(/name/i);
			await user.clear(input);
			await user.type(input, "Jane Doe");
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockApiPatch).toHaveBeenCalledWith("/auth/profile", {
					name: "Jane Doe",
				});
			});
		});

		it("shows success toast after name update", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: { ...VERIFIED_SESSION.session, name: "Jane Doe" },
			});
			const user = renderAccount();

			await user.click(screen.getByRole("button", { name: /edit.*name/i }));
			const input = screen.getByLabelText(/name/i);
			await user.clear(input);
			await user.type(input, "Jane Doe");
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalled();
			});
		});

		it("hides name input after successful save", async () => {
			mocks.mockApiPatch.mockResolvedValueOnce({
				data: { ...VERIFIED_SESSION.session, name: "Jane Doe" },
			});
			const user = renderAccount();

			await user.click(screen.getByRole("button", { name: /edit.*name/i }));
			const input = screen.getByLabelText(/name/i);
			await user.clear(input);
			await user.type(input, "Jane Doe");
			await user.click(screen.getByRole("button", { name: /save/i }));

			await waitFor(() => {
				expect(
					screen.queryByRole("textbox", { name: /name/i }),
				).not.toBeInTheDocument();
			});
		});

		it("shows cancel button in edit mode", async () => {
			const user = renderAccount();

			await user.click(screen.getByRole("button", { name: /edit.*name/i }));

			expect(
				screen.getByRole("button", { name: /cancel/i }),
			).toBeInTheDocument();
		});

		it("restores original name on cancel", async () => {
			const user = renderAccount();

			await user.click(screen.getByRole("button", { name: /edit.*name/i }));
			const input = screen.getByLabelText(/name/i);
			await user.clear(input);
			await user.type(input, "Changed Name");
			await user.click(screen.getByRole("button", { name: /cancel/i }));

			expect(screen.getByText("Jane Smith")).toBeInTheDocument();
			expect(
				screen.queryByRole("textbox", { name: /name/i }),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Password change
	// -----------------------------------------------------------------------

	describe("password change", () => {
		it("shows password form when Change password is clicked", async () => {
			const user = renderAccount();

			await user.click(
				screen.getByRole("button", { name: /change password/i }),
			);

			expect(screen.getByLabelText(/current password/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/^new password$/i)).toBeInTheDocument();
			expect(
				screen.getByLabelText(/confirm new password/i),
			).toBeInTheDocument();
		});

		it("does not show current password field for OAuth-only user", async () => {
			mocks.mockUseSession.mockReturnValue(OAUTH_ONLY_SESSION);
			const user = renderAccount();

			await user.click(screen.getByRole("button", { name: /set a password/i }));

			expect(
				screen.queryByLabelText(/current password/i),
			).not.toBeInTheDocument();
			expect(screen.getByLabelText(/^new password$/i)).toBeInTheDocument();
		});

		it("calls change-password API with correct body", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({
				data: { message: "Password updated" },
			});
			const user = renderAccount();

			await user.click(
				screen.getByRole("button", { name: /change password/i }),
			);
			await user.type(screen.getByLabelText(/current password/i), "OldP@ss1!");
			await user.type(screen.getByLabelText(/^new password$/i), "NewP@ss2!");
			await user.type(
				screen.getByLabelText(/confirm new password/i),
				"NewP@ss2!",
			);
			await user.click(screen.getByTestId("password-submit"));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					"/auth/change-password",
					{
						current_password: "OldP@ss1!",
						new_password: "NewP@ss2!",
					},
				);
			});
		});

		it("sends null current_password for OAuth-only user", async () => {
			mocks.mockUseSession.mockReturnValue(OAUTH_ONLY_SESSION);
			mocks.mockApiPost.mockResolvedValueOnce({
				data: { message: "Password updated" },
			});
			const user = renderAccount();

			await user.click(screen.getByRole("button", { name: /set a password/i }));
			await user.type(screen.getByLabelText(/^new password$/i), "NewP@ss2!");
			await user.type(
				screen.getByLabelText(/confirm new password/i),
				"NewP@ss2!",
			);
			await user.click(screen.getByTestId("password-submit"));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					"/auth/change-password",
					{
						current_password: null,
						new_password: "NewP@ss2!",
					},
				);
			});
		});

		it("shows success toast after password change", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({
				data: { message: "Password updated" },
			});
			const user = renderAccount();

			await user.click(
				screen.getByRole("button", { name: /change password/i }),
			);
			await user.type(screen.getByLabelText(/current password/i), "OldP@ss1!");
			await user.type(screen.getByLabelText(/^new password$/i), "NewP@ss2!");
			await user.type(
				screen.getByLabelText(/confirm new password/i),
				"NewP@ss2!",
			);
			await user.click(screen.getByTestId("password-submit"));

			await waitFor(() => {
				expect(mocks.mockShowToast.success).toHaveBeenCalled();
			});
		});

		it("shows error when new passwords do not match", async () => {
			const user = renderAccount();

			await user.click(
				screen.getByRole("button", { name: /change password/i }),
			);
			await user.type(screen.getByLabelText(/current password/i), "OldP@ss1!");
			await user.type(screen.getByLabelText(/^new password$/i), "NewP@ss2!");
			await user.type(
				screen.getByLabelText(/confirm new password/i),
				"DifferentP@ss3!",
			);
			await user.click(screen.getByTestId("password-submit"));

			await waitFor(() => {
				expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
			});
			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});

		it("shows error for password validation failure (400)", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError(
					"VALIDATION_ERROR",
					"Password must contain at least one special character",
					400,
				),
			);
			const user = renderAccount();

			await user.click(
				screen.getByRole("button", { name: /change password/i }),
			);
			await user.type(screen.getByLabelText(/current password/i), "OldP@ss1!");
			await user.type(screen.getByLabelText(/^new password$/i), "weakpass");
			await user.type(
				screen.getByLabelText(/confirm new password/i),
				"weakpass",
			);
			await user.click(screen.getByTestId("password-submit"));

			await waitFor(() => {
				expect(
					screen.getByText(/does not meet requirements/i),
				).toBeInTheDocument();
			});
		});

		it("shows error for incorrect current password (401)", async () => {
			mocks.mockApiPost.mockRejectedValueOnce(
				new mocks.MockApiError(
					"UNAUTHORIZED",
					"Current password incorrect",
					401,
				),
			);
			const user = renderAccount();

			await user.click(
				screen.getByRole("button", { name: /change password/i }),
			);
			await user.type(screen.getByLabelText(/current password/i), "WrongP@ss!");
			await user.type(screen.getByLabelText(/^new password$/i), "NewP@ss2!");
			await user.type(
				screen.getByLabelText(/confirm new password/i),
				"NewP@ss2!",
			);
			await user.click(screen.getByTestId("password-submit"));

			await waitFor(() => {
				expect(
					screen.getByText(/current password.*incorrect/i),
				).toBeInTheDocument();
			});
		});

		it("hides password form after successful change", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({
				data: { message: "Password updated" },
			});
			const user = renderAccount();

			await user.click(
				screen.getByRole("button", { name: /change password/i }),
			);
			await user.type(screen.getByLabelText(/current password/i), "OldP@ss1!");
			await user.type(screen.getByLabelText(/^new password$/i), "NewP@ss2!");
			await user.type(
				screen.getByLabelText(/confirm new password/i),
				"NewP@ss2!",
			);
			await user.click(screen.getByTestId("password-submit"));

			await waitFor(() => {
				expect(
					screen.queryByLabelText(/current password/i),
				).not.toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Sign out
	// -----------------------------------------------------------------------

	describe("sign out", () => {
		it("calls logout API when Sign out is clicked", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({
				data: { message: "Signed out" },
			});
			const user = renderAccount();

			await user.click(screen.getByRole("button", { name: /^sign out$/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith("/auth/logout");
			});
		});

		it("redirects to /login after sign out", async () => {
			mocks.mockApiPost.mockResolvedValueOnce({
				data: { message: "Signed out" },
			});
			const user = renderAccount();

			await user.click(screen.getByRole("button", { name: /^sign out$/i }));

			await waitFor(() => {
				expect(mocks.mockLocationHref).toHaveBeenCalledWith("/login");
			});
		});
	});

	// -----------------------------------------------------------------------
	// Sign out all devices
	// -----------------------------------------------------------------------

	describe("sign out all devices", () => {
		it("shows confirmation dialog when clicked", async () => {
			const user = renderAccount();

			await user.click(
				screen.getByRole("button", { name: /sign out.*all devices/i }),
			);

			expect(
				screen.getByText(/this will sign you out.*everywhere/i),
			).toBeInTheDocument();
		});

		it("calls invalidate-sessions API on confirm", async () => {
			// First call: invalidate-sessions; second: logout
			mocks.mockApiPost
				.mockResolvedValueOnce({
					data: { message: "All sessions invalidated" },
				})
				.mockResolvedValueOnce({
					data: { message: "Signed out" },
				});
			const user = renderAccount();

			await user.click(
				screen.getByRole("button", { name: /sign out.*all devices/i }),
			);
			await user.click(screen.getByRole("button", { name: /confirm/i }));

			await waitFor(() => {
				expect(mocks.mockApiPost).toHaveBeenCalledWith(
					"/auth/invalidate-sessions",
				);
			});
		});

		it("does not call API when cancelled", async () => {
			const user = renderAccount();

			await user.click(
				screen.getByRole("button", { name: /sign out.*all devices/i }),
			);
			await user.click(screen.getByRole("button", { name: /cancel/i }));

			expect(mocks.mockApiPost).not.toHaveBeenCalled();
		});
	});
});
