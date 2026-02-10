/**
 * Tests for FormTextareaField component.
 *
 * REQ-012 §13.2: Inline errors below each field on blur.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";
import { z } from "zod";

import { Form } from "@/components/ui/form";

import { FormTextareaField } from "./form-textarea-field";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BIO_PLACEHOLDER = "Tell us about yourself";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

const schema = z.object({
	bio: z.string().min(10, "Bio must be at least 10 characters"),
});

type TestValues = z.infer<typeof schema>;

function TestForm({ disabled }: { disabled?: boolean }) {
	const form = useForm<TestValues>({
		resolver: zodResolver(schema),
		defaultValues: { bio: "" },
		mode: "onBlur",
	});
	return (
		<Form {...form}>
			<form onSubmit={form.handleSubmit(() => {})}>
				<FormTextareaField
					control={form.control}
					name="bio"
					label="Bio"
					placeholder={BIO_PLACEHOLDER}
					description="A short bio for your profile"
					disabled={disabled}
					rows={4}
				/>
				<button type="submit">Submit</button>
			</form>
		</Form>
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FormTextareaField", () => {
	it("renders label text", () => {
		render(<TestForm />);
		expect(screen.getByText("Bio")).toBeInTheDocument();
	});

	it("renders placeholder text", () => {
		render(<TestForm />);
		expect(screen.getByPlaceholderText(BIO_PLACEHOLDER)).toBeInTheDocument();
	});

	it("renders description text", () => {
		render(<TestForm />);
		expect(
			screen.getByText("A short bio for your profile"),
		).toBeInTheDocument();
	});

	it("shows inline validation error on blur", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		const textarea = screen.getByPlaceholderText(BIO_PLACEHOLDER);
		await user.click(textarea);
		await user.type(textarea, "Short");
		await user.tab();

		await waitFor(() => {
			expect(
				screen.getByText("Bio must be at least 10 characters"),
			).toBeInTheDocument();
		});
	});

	it("disables the textarea when disabled prop is true", () => {
		render(<TestForm disabled />);
		expect(screen.getByPlaceholderText(BIO_PLACEHOLDER)).toBeDisabled();
	});

	it("passes rows attribute", () => {
		render(<TestForm />);
		expect(screen.getByPlaceholderText(BIO_PLACEHOLDER)).toHaveAttribute(
			"rows",
			"4",
		);
	});
});
