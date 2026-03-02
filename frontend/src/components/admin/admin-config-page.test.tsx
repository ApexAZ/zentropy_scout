/**
 * Tests for the admin config page layout component.
 *
 * REQ-022 §11.1–§11.2: Tab navigation with 6 tabs,
 * correct tab shown on click, default tab selection.
 */

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AdminConfigPage } from "./admin-config-page";

// ---------------------------------------------------------------------------
// Mocks — stub child tab components to isolate page layout tests
// ---------------------------------------------------------------------------

vi.mock("./models-tab", () => ({
	ModelsTab: () => <div data-testid="models-tab-content">Models Tab</div>,
}));

vi.mock("./pricing-tab", () => ({
	PricingTab: () => <div data-testid="pricing-tab-content">Pricing Tab</div>,
}));

vi.mock("./routing-tab", () => ({
	RoutingTab: () => <div data-testid="routing-tab-content">Routing Tab</div>,
}));

vi.mock("./packs-tab", () => ({
	PacksTab: () => <div data-testid="packs-tab-content">Packs Tab</div>,
}));

vi.mock("./system-tab", () => ({
	SystemTab: () => <div data-testid="system-tab-content">System Tab</div>,
}));

vi.mock("./users-tab", () => ({
	UsersTab: () => <div data-testid="users-tab-content">Users Tab</div>,
}));

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
});

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AdminConfigPage", () => {
	it("renders page heading", () => {
		render(<AdminConfigPage />);
		expect(
			screen.getByRole("heading", { name: /admin configuration/i }),
		).toBeInTheDocument();
	});

	it("renders all 6 tab triggers", () => {
		render(<AdminConfigPage />);
		expect(screen.getByRole("tab", { name: /models/i })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: /pricing/i })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: /routing/i })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: /packs/i })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: /system/i })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: /users/i })).toBeInTheDocument();
	});

	it("shows Models tab content by default", () => {
		render(<AdminConfigPage />);
		expect(screen.getByTestId("models-tab-content")).toBeInTheDocument();
	});

	it("switches to Pricing tab on click", async () => {
		const user = userEvent.setup();
		render(<AdminConfigPage />);
		await user.click(screen.getByRole("tab", { name: /pricing/i }));
		expect(screen.getByTestId("pricing-tab-content")).toBeInTheDocument();
	});

	it("switches to Routing tab on click", async () => {
		const user = userEvent.setup();
		render(<AdminConfigPage />);
		await user.click(screen.getByRole("tab", { name: /routing/i }));
		expect(screen.getByTestId("routing-tab-content")).toBeInTheDocument();
	});

	it("switches to Packs tab on click", async () => {
		const user = userEvent.setup();
		render(<AdminConfigPage />);
		await user.click(screen.getByRole("tab", { name: /packs/i }));
		expect(screen.getByTestId("packs-tab-content")).toBeInTheDocument();
	});

	it("switches to System tab on click", async () => {
		const user = userEvent.setup();
		render(<AdminConfigPage />);
		await user.click(screen.getByRole("tab", { name: /system/i }));
		expect(screen.getByTestId("system-tab-content")).toBeInTheDocument();
	});

	it("switches to Users tab on click", async () => {
		const user = userEvent.setup();
		render(<AdminConfigPage />);
		await user.click(screen.getByRole("tab", { name: /users/i }));
		expect(screen.getByTestId("users-tab-content")).toBeInTheDocument();
	});

	it("has data-testid on page container", () => {
		render(<AdminConfigPage />);
		expect(screen.getByTestId("admin-config-page")).toBeInTheDocument();
	});
});
