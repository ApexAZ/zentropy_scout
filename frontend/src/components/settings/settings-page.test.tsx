/**
 * Tests for the SettingsPage component (§11.1).
 *
 * REQ-012 §12.1: Settings page layout with Account, Agent Configuration,
 * and About sections.
 * REQ-024 §5.4: Legal section with ToS and Privacy links.
 * REQ-034 §9.2: Job Search section with search criteria, poll schedule, sources.
 */

import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("next/link", () => ({
	default: function MockLink({
		children,
		href,
		...props
	}: {
		children: ReactNode;
		href: string;
		[key: string]: unknown;
	}) {
		return (
			<a href={href} {...props}>
				{children}
			</a>
		);
	},
}));

vi.mock("./account-section", () => ({
	AccountSection: () => <div data-testid="mock-account-section" />,
}));

vi.mock("./agent-configuration-section", () => ({
	AgentConfigurationSection: () => (
		<div data-testid="mock-agent-configuration-section" />
	),
}));

vi.mock("./job-search-section", () => ({
	JobSearchSection: ({ personaId }: { personaId: string }) => (
		<div data-testid="mock-job-search-section" data-persona-id={personaId} />
	),
}));

import { SettingsPage } from "./settings-page";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PAGE_TESTID = "settings-page";
const ACCOUNT_TESTID = "settings-account";
const JOB_SEARCH_TESTID = "settings-job-search";
const AGENT_CONFIG_TESTID = "settings-agent-configuration";
const ABOUT_TESTID = "settings-about";
const LEGAL_TESTID = "settings-legal";
const PERSONA_ID = "p-1";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SettingsPage", () => {
	afterEach(() => {
		cleanup();
	});

	it("renders settings page container", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		expect(screen.getByTestId(PAGE_TESTID)).toBeInTheDocument();
	});

	it("displays 'Settings' heading", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		expect(
			screen.getByRole("heading", { name: "Settings", level: 1 }),
		).toBeInTheDocument();
	});

	it("renders Job Search section with title", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(JOB_SEARCH_TESTID);
		expect(section).toBeInTheDocument();
		expect(section).toHaveTextContent("Job Search");
	});

	it("renders Agent Configuration section with title", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(AGENT_CONFIG_TESTID);
		expect(section).toBeInTheDocument();
		expect(section).toHaveTextContent("Agent Configuration");
	});

	it("renders About section with title", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(ABOUT_TESTID);
		expect(section).toBeInTheDocument();
		expect(section).toHaveTextContent("About");
	});

	it("renders JobSearchSection in the Job Search card", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const mockChild = screen.getByTestId("mock-job-search-section");
		expect(mockChild).toBeInTheDocument();
		expect(mockChild).toHaveAttribute("data-persona-id", PERSONA_ID);
	});

	it("renders AgentConfigurationSection in the Agent Configuration card", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const mockChild = screen.getByTestId("mock-agent-configuration-section");
		expect(mockChild).toBeInTheDocument();
	});

	it("shows version info in About section", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(ABOUT_TESTID);
		expect(section).toHaveTextContent("Zentropy Scout");
		expect(section).toHaveTextContent("AGPL-3.0");
	});

	it("shows description in About section", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(ABOUT_TESTID);
		expect(section).toHaveTextContent("AI-Powered Job Application Assistant");
	});

	it("renders Account section with title", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(ACCOUNT_TESTID);
		expect(section).toBeInTheDocument();
		expect(section).toHaveTextContent("Account");
	});

	it("renders AccountSection in the Account card", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		expect(screen.getByTestId("mock-account-section")).toBeInTheDocument();
	});

	it("renders Legal section with title", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(LEGAL_TESTID);
		expect(section).toBeInTheDocument();
		expect(section).toHaveTextContent("Legal");
	});

	it("shows Terms of Service link in Legal section", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(LEGAL_TESTID);
		expect(section).toHaveTextContent("Terms of Service");
	});

	it("shows Privacy Policy link in Legal section", () => {
		render(<SettingsPage personaId={PERSONA_ID} />);
		const section = screen.getByTestId(LEGAL_TESTID);
		expect(section).toHaveTextContent("Privacy Policy");
	});
});
