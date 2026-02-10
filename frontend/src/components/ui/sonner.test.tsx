import { act, render, screen, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { describe, expect, it } from "vitest";

import { Toaster } from "./sonner";

/** Trigger a toast so Sonner renders the full toaster list. */
function renderWithToast(props: Parameters<typeof Toaster>[0] = {}) {
	render(<Toaster {...props} />);
	act(() => {
		toast("test");
	});
}

describe("Toaster", () => {
	it("renders the notification container", () => {
		render(<Toaster />);
		expect(screen.getByLabelText(/Notifications/)).toBeInTheDocument();
	});

	it("has aria-live polite for accessibility (REQ-012 §13.8)", () => {
		render(<Toaster />);
		const region = screen.getByLabelText(/Notifications/);
		expect(region).toHaveAttribute("aria-live", "polite");
	});

	it("enables rich colors for semantic variants", async () => {
		renderWithToast();
		await waitFor(() => {
			const toastItem = document.querySelector("[data-sonner-toast]");
			expect(toastItem).not.toBeNull();
			expect(toastItem).toHaveAttribute("data-rich-colors", "true");
		});
	});

	it("renders close button on toasts", async () => {
		renderWithToast();
		await waitFor(() => {
			const closeBtn = screen.getByLabelText("Close toast");
			expect(closeBtn).toBeInTheDocument();
			expect(closeBtn).toHaveAttribute("data-close-button", "true");
		});
	});

	it("accepts a position override", async () => {
		renderWithToast({ position: "top-center" });
		await waitFor(() => {
			const toaster = document.querySelector("[data-sonner-toaster]");
			expect(toaster).not.toBeNull();
			expect(toaster).toHaveAttribute("data-x-position", "center");
			expect(toaster).toHaveAttribute("data-y-position", "top");
		});
	});
});
