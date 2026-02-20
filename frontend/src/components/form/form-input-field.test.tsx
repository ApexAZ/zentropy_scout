/**
 * Tests for FormInputField component.
 *
 * REQ-012 §13.2: Inline errors below each field on blur.
 * Client-side validation via Zod; disabled inputs during submission.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";
import { z } from "zod";

import { Form } from "@/components/ui/form";

import { FormInputField } from "./form-input-field";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NAME_PLACEHOLDER = "Enter your name";
const NAME_MIN_ERROR = "Name must be at least 2 characters";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

const schema = z.object({
	name: z.string().min(2, NAME_MIN_ERROR),
	email: z.string().pipe(z.email({ message: "Invalid email address" })),
	age: z.string().min(1, { message: "Age is required" }),
});

type TestValues = z.infer<typeof schema>;

function TestForm({ disabled }: { disabled?: boolean }) {
	const form = useForm<TestValues>({
		resolver: zodResolver(schema),
		defaultValues: { name: "", email: "", age: "" },
		mode: "onBlur",
	});
	return (
		<Form {...form}>
			<form onSubmit={form.handleSubmit(() => {})}>
				<FormInputField
					control={form.control}
					name="name"
					label="Full Name"
					placeholder={NAME_PLACEHOLDER}
					description="Your legal full name"
					disabled={disabled}
				/>
				<FormInputField
					control={form.control}
					name="email"
					label="Email"
					placeholder="you@example.com"
					type="email"
				/>
				<FormInputField
					control={form.control}
					name="age"
					label="Age"
					type="number"
					min={1}
					max={120}
					step={1}
				/>
				<button type="submit">Submit</button>
			</form>
		</Form>
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FormInputField", () => {
	it("renders label text", () => {
		render(<TestForm />);
		expect(screen.getByText("Full Name")).toBeInTheDocument();
	});

	it("renders placeholder text", () => {
		render(<TestForm />);
		expect(screen.getByPlaceholderText(NAME_PLACEHOLDER)).toBeInTheDocument();
	});

	it("renders description text", () => {
		render(<TestForm />);
		expect(screen.getByText("Your legal full name")).toBeInTheDocument();
	});

	it("shows inline validation error on blur", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		const input = screen.getByPlaceholderText(NAME_PLACEHOLDER);
		await user.click(input);
		await user.type(input, "A");
		await user.tab();

		await waitFor(() => {
			expect(screen.getByText(NAME_MIN_ERROR)).toBeInTheDocument();
		});
	});

	it("clears error when valid value is entered", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		const input = screen.getByPlaceholderText(NAME_PLACEHOLDER);
		await user.click(input);
		await user.type(input, "A");
		await user.tab();

		await waitFor(() => {
			expect(screen.getByText(NAME_MIN_ERROR)).toBeInTheDocument();
		});

		await user.clear(input);
		await user.type(input, "Alice");
		await user.tab();

		await waitFor(() => {
			expect(screen.queryByText(NAME_MIN_ERROR)).not.toBeInTheDocument();
		});
	});

	it("disables the input when disabled prop is true", () => {
		render(<TestForm disabled />);
		expect(screen.getByPlaceholderText(NAME_PLACEHOLDER)).toBeDisabled();
	});

	it("renders with specified input type", () => {
		render(<TestForm />);
		const emailInput = screen.getByPlaceholderText("you@example.com");
		expect(emailInput).toHaveAttribute("type", "email");
	});

	it("passes number input attributes", () => {
		render(<TestForm />);
		const ageInput = screen.getByRole("spinbutton", { name: "Age" });
		expect(ageInput).toHaveAttribute("type", "number");
		expect(ageInput).toHaveAttribute("min", "1");
		expect(ageInput).toHaveAttribute("max", "120");
		expect(ageInput).toHaveAttribute("step", "1");
	});
});
