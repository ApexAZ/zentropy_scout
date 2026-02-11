/**
 * Tests for the Sheet component.
 *
 * REQ-012 §5.1: Side sheet for tablet/mobile chat panel overlay.
 * Built on Radix Dialog primitive following shadcn patterns.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
	Sheet,
	SheetClose,
	SheetContent,
	SheetHeader,
	SheetTitle,
} from "./sheet";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderSheet(
	props: {
		open?: boolean;
		onOpenChange?: (open: boolean) => void;
		side?: "top" | "right" | "bottom" | "left";
		contentClassName?: string;
		children?: React.ReactNode;
	} = {},
) {
	const {
		open = true,
		onOpenChange = vi.fn(),
		side,
		contentClassName,
		children,
	} = props;

	return render(
		<Sheet open={open} onOpenChange={onOpenChange}>
			<SheetContent side={side} className={contentClassName}>
				<SheetHeader>
					<SheetTitle>Test Sheet</SheetTitle>
				</SheetHeader>
				{children ?? <p>Sheet body content</p>}
				<SheetClose>Close me</SheetClose>
			</SheetContent>
		</Sheet>,
	);
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SHEET_CONTENT_SELECTOR = '[data-slot="sheet-content"]';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Sheet", () => {
	it("renders content when open", () => {
		renderSheet();

		expect(screen.getByText("Sheet body content")).toBeInTheDocument();
	});

	it("does not render content when closed", () => {
		renderSheet({ open: false });

		expect(screen.queryByText("Sheet body content")).not.toBeInTheDocument();
	});

	it("has data-slot='sheet-content' on content", () => {
		renderSheet();

		expect(document.querySelector(SHEET_CONTENT_SELECTOR)).toBeInTheDocument();
	});

	it("applies side prop as data-side attribute", () => {
		renderSheet({ side: "left" });

		const content = document.querySelector(SHEET_CONTENT_SELECTOR);
		expect(content).toHaveAttribute("data-side", "left");
	});

	it("defaults to side='right'", () => {
		renderSheet();

		const content = document.querySelector(SHEET_CONTENT_SELECTOR);
		expect(content).toHaveAttribute("data-side", "right");
	});

	it("renders overlay backdrop when open", () => {
		renderSheet();

		expect(
			document.querySelector('[data-slot="sheet-overlay"]'),
		).toBeInTheDocument();
	});

	it("has accessible title via SheetTitle", () => {
		renderSheet();

		expect(
			screen.getByRole("heading", { name: "Test Sheet" }),
		).toBeInTheDocument();
	});

	it("has dialog role on content", () => {
		renderSheet();

		expect(screen.getByRole("dialog")).toBeInTheDocument();
	});
});
