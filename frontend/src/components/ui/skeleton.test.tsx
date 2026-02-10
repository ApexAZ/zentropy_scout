import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Skeleton } from "./skeleton";

describe("Skeleton", () => {
	it("renders a div element", () => {
		render(<Skeleton data-testid="skeleton" />);
		const el = screen.getByTestId("skeleton");
		expect(el.tagName).toBe("DIV");
	});

	it("has animate-pulse class", () => {
		render(<Skeleton data-testid="skeleton" />);
		expect(screen.getByTestId("skeleton")).toHaveClass("animate-pulse");
	});

	it("has default background class", () => {
		render(<Skeleton data-testid="skeleton" />);
		expect(screen.getByTestId("skeleton")).toHaveClass("bg-primary/10");
	});

	it("merges custom className with defaults", () => {
		render(<Skeleton data-testid="skeleton" className="h-4 w-32" />);
		const el = screen.getByTestId("skeleton");
		expect(el).toHaveClass("animate-pulse");
		expect(el).toHaveClass("bg-primary/10");
		expect(el).toHaveClass("h-4");
		expect(el).toHaveClass("w-32");
	});

	it("spreads additional props", () => {
		render(<Skeleton data-testid="skeleton" aria-hidden="true" />);
		expect(screen.getByTestId("skeleton")).toHaveAttribute(
			"aria-hidden",
			"true",
		);
	});
});
