/**
 * Tests for the Users tab component.
 *
 * REQ-022 §11.2, §10.6: Admin user management — table display,
 * admin toggle, env-protected badge, pagination.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AdminUserItem } from "@/types/admin";

import { UsersTab } from "./users-tab";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockFetchUsers = vi.fn();
	const mockToggleAdmin = vi.fn();
	return { mockFetchUsers, mockToggleAdmin };
});

vi.mock("@/lib/api/admin", () => ({
	fetchUsers: mocks.mockFetchUsers,
	toggleAdmin: mocks.mockToggleAdmin,
}));

vi.mock("@/lib/toast", () => ({
	showToast: {
		success: vi.fn(),
		error: vi.fn(),
		warning: vi.fn(),
		info: vi.fn(),
		dismiss: vi.fn(),
	},
}));

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const MOCK_TIMESTAMP = "2026-03-01T00:00:00Z";
const MOCK_ADMIN_EMAIL = "admin@example.com";
const MOCK_USER_EMAIL = "user@example.com";

const MOCK_USERS: AdminUserItem[] = [
	{
		id: "u-1",
		email: MOCK_ADMIN_EMAIL,
		name: "Admin User",
		is_admin: true,
		is_env_protected: true,
		balance_usd: "10.00",
		created_at: MOCK_TIMESTAMP,
	},
	{
		id: "u-2",
		email: MOCK_USER_EMAIL,
		name: "Regular User",
		is_admin: false,
		is_env_protected: false,
		balance_usd: "5.50",
		created_at: MOCK_TIMESTAMP,
	},
];

const MOCK_USERS_RESPONSE = {
	data: MOCK_USERS,
	meta: {
		total: 2,
		page: 1,
		per_page: 50,
		total_pages: 1,
	},
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createQueryClient() {
	return new QueryClient({
		defaultOptions: {
			queries: { retry: false },
			mutations: { retry: false },
		},
	});
}

function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
	const queryClient = createQueryClient();
	return (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
}

async function waitForDataLoaded() {
	await waitFor(() => {
		expect(screen.getByText(MOCK_ADMIN_EMAIL)).toBeInTheDocument();
	});
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	mocks.mockFetchUsers.mockResolvedValue(MOCK_USERS_RESPONSE);
});

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("UsersTab", () => {
	it("renders loading state initially", () => {
		mocks.mockFetchUsers.mockReturnValue(new Promise(() => {}));
		render(<UsersTab />, { wrapper: Wrapper });
		expect(screen.getByTestId("users-loading")).toBeInTheDocument();
	});

	it("renders user table with data", async () => {
		render(<UsersTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText(MOCK_USER_EMAIL)).toBeInTheDocument();
	});

	it("displays user names", async () => {
		render(<UsersTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText("Admin User")).toBeInTheDocument();
		expect(screen.getByText("Regular User")).toBeInTheDocument();
	});

	it("shows admin status", async () => {
		render(<UsersTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		const rows = screen.getAllByRole("row");
		expect(rows[1]).toHaveTextContent("Admin");
	});

	it("shows env-protected badge for protected admins", async () => {
		render(<UsersTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText("Protected")).toBeInTheDocument();
	});

	it("displays balance", async () => {
		render(<UsersTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText("$10.00")).toBeInTheDocument();
		expect(screen.getByText("$5.50")).toBeInTheDocument();
	});

	it("toggles admin status on button click", async () => {
		const user = userEvent.setup();
		mocks.mockToggleAdmin.mockResolvedValue({
			data: { ...MOCK_USERS[1], is_admin: true },
		});
		render(<UsersTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		// The non-admin user should have a "Make Admin" button
		const promoteButton = screen.getByRole("button", {
			name: /make admin/i,
		});
		await user.click(promoteButton);
		await waitFor(() => {
			expect(mocks.mockToggleAdmin).toHaveBeenCalledWith("u-2", true);
		});
	});

	it("disables toggle for env-protected admins", async () => {
		render(<UsersTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		const removeButton = screen.getByRole("button", {
			name: /remove admin/i,
		});
		expect(removeButton).toBeDisabled();
	});

	it("shows pagination info", async () => {
		render(<UsersTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByText(/2 user/i)).toBeInTheDocument();
	});

	it("renders error state on fetch failure", async () => {
		mocks.mockFetchUsers.mockRejectedValue(new Error("Network error"));
		render(<UsersTab />, { wrapper: Wrapper });
		await waitFor(() => {
			expect(screen.getByText(/failed/i)).toBeInTheDocument();
		});
	});

	it("supports pagination controls", async () => {
		mocks.mockFetchUsers.mockResolvedValue({
			data: MOCK_USERS,
			meta: {
				total: 100,
				page: 1,
				per_page: 50,
				total_pages: 2,
			},
		});
		render(<UsersTab />, { wrapper: Wrapper });
		await waitForDataLoaded();
		expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
	});
});
