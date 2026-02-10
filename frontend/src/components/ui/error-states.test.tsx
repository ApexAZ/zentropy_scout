import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
	ConflictState,
	EmptyState,
	FailedState,
	NotFoundState,
} from "./error-states";

describe("EmptyState", () => {
	it("renders title text", () => {
		render(<EmptyState title="No resumes yet" />);
		expect(screen.getByText("No resumes yet")).toBeInTheDocument();
	});

	it("renders description when provided", () => {
		render(
			<EmptyState
				title="No resumes yet"
				description="Create your first resume to get started."
			/>,
		);
		expect(
			screen.getByText("Create your first resume to get started."),
		).toBeInTheDocument();
	});

	it("renders action button and calls onClick when clicked", async () => {
		const user = userEvent.setup();
		const handleClick = vi.fn();
		render(
			<EmptyState
				title="No resumes yet"
				action={{ label: "Create Resume", onClick: handleClick }}
			/>,
		);
		await user.click(screen.getByRole("button", { name: "Create Resume" }));
		expect(handleClick).toHaveBeenCalledOnce();
	});

	it("renders custom icon", () => {
		const CustomIcon = ({ className }: { className?: string }) => (
			<svg data-testid="custom-icon" className={className} />
		);
		render(<EmptyState icon={CustomIcon} title="Empty" />);
		expect(screen.getByTestId("custom-icon")).toBeInTheDocument();
	});

	it("has role status for accessibility", () => {
		render(<EmptyState title="No items yet" />);
		expect(screen.getByRole("status")).toBeInTheDocument();
	});
});

describe("FailedState", () => {
	it("renders default failure message", () => {
		render(<FailedState />);
		expect(screen.getByText("Failed to load.")).toBeInTheDocument();
	});

	it("renders custom message", () => {
		render(<FailedState message="Could not fetch jobs." />);
		expect(screen.getByText("Could not fetch jobs.")).toBeInTheDocument();
	});

	it("shows error code when provided", () => {
		render(<FailedState errorCode="NETWORK_ERROR" />);
		expect(screen.getByText("NETWORK_ERROR")).toBeInTheDocument();
	});

	it("calls onRetry when retry button is clicked", async () => {
		const user = userEvent.setup();
		const handleRetry = vi.fn();
		render(<FailedState onRetry={handleRetry} />);
		await user.click(screen.getByRole("button", { name: "Retry" }));
		expect(handleRetry).toHaveBeenCalledOnce();
	});

	it("has role alert for accessibility", () => {
		render(<FailedState />);
		expect(screen.getByRole("alert")).toBeInTheDocument();
	});
});

describe("NotFoundState", () => {
	it("renders message with item type", () => {
		render(<NotFoundState itemType="resume" />);
		expect(
			screen.getByText("This resume doesn\u2019t exist."),
		).toBeInTheDocument();
	});

	it("calls onBack when go back button is clicked", async () => {
		const user = userEvent.setup();
		const handleBack = vi.fn();
		render(<NotFoundState onBack={handleBack} />);
		await user.click(screen.getByRole("button", { name: "Go back" }));
		expect(handleBack).toHaveBeenCalledOnce();
	});

	it("renders default item type when not provided", () => {
		render(<NotFoundState />);
		expect(
			screen.getByText("This item doesn\u2019t exist."),
		).toBeInTheDocument();
	});

	it("has role alert for accessibility", () => {
		render(<NotFoundState />);
		expect(screen.getByRole("alert")).toBeInTheDocument();
	});
});

describe("ConflictState", () => {
	it("renders default conflict message", () => {
		render(<ConflictState />);
		expect(screen.getByText("This was modified.")).toBeInTheDocument();
	});

	it("renders custom message", () => {
		render(<ConflictState message="Resume was updated by an agent." />);
		expect(
			screen.getByText("Resume was updated by an agent."),
		).toBeInTheDocument();
	});

	it("calls onRefresh when refresh button is clicked", async () => {
		const user = userEvent.setup();
		const handleRefresh = vi.fn();
		render(<ConflictState onRefresh={handleRefresh} />);
		await user.click(screen.getByRole("button", { name: "Refresh" }));
		expect(handleRefresh).toHaveBeenCalledOnce();
	});

	it("has role alert for accessibility", () => {
		render(<ConflictState />);
		expect(screen.getByRole("alert")).toBeInTheDocument();
	});
});
