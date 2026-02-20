/**
 * Tests for FormErrorSummary component.
 *
 * REQ-012 §13.2: Form-level error summary on submit failure.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";
import { z } from "zod";

import { Form } from "@/components/ui/form";

import { FormErrorSummary } from "./form-error-summary";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SUBMIT_LABEL = "Submit";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

const schema = z.object({
	name: z.string().min(1, { message: "Name is required" }),
	email: z.string().pipe(z.email({ message: "Invalid email address" })),
});

type TestValues = z.infer<typeof schema>;

function TestForm() {
	const form = useForm<TestValues>({
		resolver: zodResolver(schema),
		defaultValues: { name: "", email: "" },
	});
	return (
		<Form {...form}>
			<form onSubmit={form.handleSubmit(() => {})}>
				<FormErrorSummary />
				<input {...form.register("name")} placeholder="Name" />
				<input {...form.register("email")} placeholder="Email" />
				<button type="submit">Submit</button>
			</form>
		</Form>
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FormErrorSummary", () => {
	it("renders nothing when there are no errors", () => {
		render(<TestForm />);
		expect(screen.queryByRole("alert")).not.toBeInTheDocument();
	});

	it("shows error summary after failed submit", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		await user.click(screen.getByText(SUBMIT_LABEL));

		await waitFor(() => {
			expect(screen.getByRole("alert")).toBeInTheDocument();
		});
		expect(screen.getByText("Name is required")).toBeInTheDocument();
		expect(screen.getByText("Invalid email address")).toBeInTheDocument();
	});

	it("shows heading text for error summary", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		await user.click(screen.getByText(SUBMIT_LABEL));

		await waitFor(() => {
			expect(
				screen.getByText("Please fix the following errors:"),
			).toBeInTheDocument();
		});
	});

	it("disappears when errors are fixed and form resubmitted", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		await user.click(screen.getByText(SUBMIT_LABEL));

		await waitFor(() => {
			expect(screen.getByRole("alert")).toBeInTheDocument();
		});

		await user.type(screen.getByPlaceholderText("Name"), "Alice");
		await user.type(screen.getByPlaceholderText("Email"), "alice@example.com");
		await user.click(screen.getByText(SUBMIT_LABEL));

		await waitFor(() => {
			expect(screen.queryByRole("alert")).not.toBeInTheDocument();
		});
	});
});
