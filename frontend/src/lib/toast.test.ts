import { toast as sonnerToast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { showToast } from "./toast";

const MOCK_TOAST_ID = "mock-id";

vi.mock("sonner", () => ({
	toast: Object.assign(
		vi.fn(() => MOCK_TOAST_ID),
		{
			success: vi.fn(() => MOCK_TOAST_ID),
			error: vi.fn(() => MOCK_TOAST_ID),
			warning: vi.fn(() => MOCK_TOAST_ID),
			info: vi.fn(() => MOCK_TOAST_ID),
			dismiss: vi.fn(),
		},
	),
}));

beforeEach(() => {
	vi.clearAllMocks();
});

describe("showToast", () => {
	it("calls toast.success with 3s duration", () => {
		showToast.success("Saved");
		expect(sonnerToast.success).toHaveBeenCalledWith("Saved", {
			duration: 3000,
		});
	});

	it("calls toast.error with Infinity duration", () => {
		showToast.error("Failed");
		expect(sonnerToast.error).toHaveBeenCalledWith("Failed", {
			duration: Infinity,
		});
	});

	it("calls toast.warning with 5s duration", () => {
		showToast.warning("Watch out");
		expect(sonnerToast.warning).toHaveBeenCalledWith("Watch out", {
			duration: 5000,
		});
	});

	it("calls toast.info with 5s duration", () => {
		showToast.info("FYI");
		expect(sonnerToast.info).toHaveBeenCalledWith("FYI", {
			duration: 5000,
		});
	});

	it("merges custom options with default duration", () => {
		showToast.success("Saved", { description: "All good" });
		expect(sonnerToast.success).toHaveBeenCalledWith("Saved", {
			duration: 3000,
			description: "All good",
		});
	});

	it("allows overriding the default duration", () => {
		showToast.info("Custom", { duration: 10000 });
		expect(sonnerToast.info).toHaveBeenCalledWith("Custom", {
			duration: 10000,
		});
	});

	it("returns a toast ID from each variant", () => {
		expect(showToast.success("ok")).toBe(MOCK_TOAST_ID);
		expect(showToast.error("fail")).toBe(MOCK_TOAST_ID);
		expect(showToast.warning("warn")).toBe(MOCK_TOAST_ID);
		expect(showToast.info("info")).toBe(MOCK_TOAST_ID);
	});

	it("calls toast.dismiss with a given ID", () => {
		showToast.dismiss("abc");
		expect(sonnerToast.dismiss).toHaveBeenCalledWith("abc");
	});

	it("calls toast.dismiss with no args to clear all", () => {
		showToast.dismiss();
		expect(sonnerToast.dismiss).toHaveBeenCalledWith(undefined);
	});
});
