/**
 * Tests for the TablePagination component.
 *
 * Shared pagination controls used by usage-table and transaction-table.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TablePagination } from "./table-pagination";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

afterEach(() => {
	cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("TablePagination", () => {
	it("renders nothing when totalPages is 1", () => {
		const { container } = render(
			<TablePagination page={1} totalPages={1} onPageChange={vi.fn()} />,
		);
		expect(container.innerHTML).toBe("");
	});

	it("renders page indicator and buttons when totalPages > 1", () => {
		render(<TablePagination page={2} totalPages={5} onPageChange={vi.fn()} />);
		expect(screen.getByText("Page 2 of 5")).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: /previous/i }),
		).toBeInTheDocument();
		expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
	});

	it("disables Previous on first page", () => {
		render(<TablePagination page={1} totalPages={3} onPageChange={vi.fn()} />);
		expect(screen.getByRole("button", { name: /previous/i })).toBeDisabled();
	});

	it("disables Next on last page", () => {
		render(<TablePagination page={3} totalPages={3} onPageChange={vi.fn()} />);
		expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
	});

	it("calls onPageChange with page - 1 when Previous is clicked", () => {
		const onPageChange = vi.fn();
		render(
			<TablePagination page={2} totalPages={3} onPageChange={onPageChange} />,
		);
		screen.getByRole("button", { name: /previous/i }).click();
		expect(onPageChange).toHaveBeenCalledWith(1);
	});

	it("calls onPageChange with page + 1 when Next is clicked", () => {
		const onPageChange = vi.fn();
		render(
			<TablePagination page={2} totalPages={3} onPageChange={onPageChange} />,
		);
		screen.getByRole("button", { name: /next/i }).click();
		expect(onPageChange).toHaveBeenCalledWith(3);
	});
});
