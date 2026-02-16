/**
 * Tests for FormSelectField component.
 *
 * REQ-012 §13.2: Inline errors below each field on blur.
 *
 * Note: Radix Select uses portals, which limits what jsdom can test.
 * We focus on rendering, label, error display, and disabled state.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";
import { z } from "zod";

import { Form } from "@/components/ui/form";

import { FormSelectField } from "./form-select-field";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

const OPTIONS = [
	{ label: "Small", value: "small" },
	{ label: "Medium", value: "medium" },
	{ label: "Large", value: "large" },
];

const schema = z.object({
	size: z.string().min(1, { message: "Size is required" }),
});

type TestValues = z.infer<typeof schema>;

function TestForm({ disabled }: { disabled?: boolean }) {
	const form = useForm<TestValues>({
		resolver: zodResolver(schema),
		defaultValues: { size: "" },
		mode: "onBlur",
	});
	return (
		<Form {...form}>
			<form onSubmit={form.handleSubmit(() => {})}>
				<FormSelectField
					control={form.control}
					name="size"
					label="Size"
					placeholder="Select a size"
					description="Choose your preferred size"
					options={OPTIONS}
					disabled={disabled}
				/>
				<button type="submit">Submit</button>
			</form>
		</Form>
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FormSelectField", () => {
	it("renders label text", () => {
		render(<TestForm />);
		expect(screen.getByText("Size")).toBeInTheDocument();
	});

	it("renders description text", () => {
		render(<TestForm />);
		expect(screen.getByText("Choose your preferred size")).toBeInTheDocument();
	});

	it("renders the select trigger", () => {
		render(<TestForm />);
		expect(screen.getByRole("combobox")).toBeInTheDocument();
	});

	it("shows validation error on submit with empty value", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		await user.click(screen.getByText("Submit"));

		await waitFor(() => {
			expect(screen.getByText("Size is required")).toBeInTheDocument();
		});
	});

	it("disables the select trigger when disabled", () => {
		render(<TestForm disabled />);
		expect(screen.getByRole("combobox")).toBeDisabled();
	});
});
