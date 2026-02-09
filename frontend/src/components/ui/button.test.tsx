import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./button";

describe("Button", () => {
	it("renders with text content", () => {
		render(<Button>Click me</Button>);
		expect(
			screen.getByRole("button", { name: "Click me" }),
		).toBeInTheDocument();
	});

	it("applies variant classes", () => {
		render(<Button variant="destructive">Delete</Button>);
		const button = screen.getByRole("button", { name: "Delete" });
		expect(button).toHaveClass("bg-destructive");
	});

	it("forwards native button attributes", () => {
		render(<Button disabled>Disabled</Button>);
		expect(screen.getByRole("button", { name: "Disabled" })).toBeDisabled();
	});
});
