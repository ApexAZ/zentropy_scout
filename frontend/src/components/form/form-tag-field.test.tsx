/**
 * Tests for FormTagField component.
 *
 * REQ-012 §13.2: Tag/chip input for JSONB string arrays.
 * Used across onboarding and persona editing for skills, cities, exclusions.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";
import { z } from "zod";

import { Form } from "@/components/ui/form";

import { FormTagField } from "./form-tag-field";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TAG_PLACEHOLDER = "Type and press Enter";
const TAG_LABEL = "Skills";
const TAG_DESCRIPTION = "Add your skills";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

const schema = z.object({
	tags: z.array(z.string()).min(1, { message: "At least one tag is required" }),
});

type TestValues = z.infer<typeof schema>;

function TestForm({
	disabled,
	maxItems,
	defaultValues,
}: {
	disabled?: boolean;
	maxItems?: number;
	defaultValues?: string[];
}) {
	const form = useForm<TestValues>({
		resolver: zodResolver(schema),
		defaultValues: { tags: defaultValues ?? [] },
		mode: "onBlur",
	});
	return (
		<Form {...form}>
			<form onSubmit={form.handleSubmit(() => {})}>
				<FormTagField
					control={form.control}
					name="tags"
					label={TAG_LABEL}
					placeholder={TAG_PLACEHOLDER}
					description={TAG_DESCRIPTION}
					disabled={disabled}
					maxItems={maxItems}
				/>
				<button type="submit">Submit</button>
			</form>
		</Form>
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FormTagField", () => {
	it("renders label text", () => {
		render(<TestForm />);
		expect(screen.getByText(TAG_LABEL)).toBeInTheDocument();
	});

	it("renders placeholder text", () => {
		render(<TestForm />);
		expect(screen.getByPlaceholderText(TAG_PLACEHOLDER)).toBeInTheDocument();
	});

	it("renders description text", () => {
		render(<TestForm />);
		expect(screen.getByText(TAG_DESCRIPTION)).toBeInTheDocument();
	});

	it("renders default tags as chips", () => {
		render(<TestForm defaultValues={["React", "TypeScript"]} />);
		expect(screen.getByText("React")).toBeInTheDocument();
		expect(screen.getByText("TypeScript")).toBeInTheDocument();
	});

	it("adds a tag on Enter key", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		const input = screen.getByPlaceholderText(TAG_PLACEHOLDER);
		await user.type(input, "React{Enter}");

		expect(screen.getByText("React")).toBeInTheDocument();
		expect(input).toHaveValue("");
	});

	it("adds a tag on comma key", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		const input = screen.getByPlaceholderText(TAG_PLACEHOLDER);
		await user.type(input, "React,");

		expect(screen.getByText("React")).toBeInTheDocument();
		expect(input).toHaveValue("");
	});

	it("removes a tag by clicking the remove button", async () => {
		const user = userEvent.setup();
		render(<TestForm defaultValues={["React", "TypeScript"]} />);

		expect(screen.getByText("React")).toBeInTheDocument();

		const reactChip = screen.getByText("React").closest("[data-slot='tag']");
		const removeButton = within(reactChip as HTMLElement).getByRole("button", {
			name: /remove react/i,
		});
		await user.click(removeButton);

		expect(screen.queryByText("React")).not.toBeInTheDocument();
		expect(screen.getByText("TypeScript")).toBeInTheDocument();
	});

	it("prevents duplicate tags (case-insensitive)", async () => {
		const user = userEvent.setup();
		render(<TestForm defaultValues={["React"]} />);

		const input = screen.getByRole("textbox");
		await user.type(input, "react{Enter}");

		const chips = screen.getAllByText(/^React$/i);
		expect(chips).toHaveLength(1);
	});

	it("prevents empty tags", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		const input = screen.getByPlaceholderText(TAG_PLACEHOLDER);
		await user.type(input, "   {Enter}");

		const tags = screen.queryAllByRole("button", { name: /remove/i });
		expect(tags).toHaveLength(0);
	});

	it("removes last tag on Backspace when input is empty", async () => {
		const user = userEvent.setup();
		render(<TestForm defaultValues={["React", "TypeScript"]} />);

		const input = screen.getByRole("textbox");
		await user.click(input);
		await user.keyboard("{Backspace}");

		expect(screen.queryByText("TypeScript")).not.toBeInTheDocument();
		expect(screen.getByText("React")).toBeInTheDocument();
	});

	it("trims whitespace from tags", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		const input = screen.getByPlaceholderText(TAG_PLACEHOLDER);
		await user.type(input, "  React  {Enter}");

		expect(screen.getByText("React")).toBeInTheDocument();
	});

	it("disables the input when disabled prop is true", () => {
		render(<TestForm disabled defaultValues={["React"]} />);
		expect(screen.getByRole("textbox")).toBeDisabled();
		expect(
			screen.queryByRole("button", { name: /remove/i }),
		).not.toBeInTheDocument();
	});

	it("shows validation error on blur with empty tags", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		const input = screen.getByPlaceholderText(TAG_PLACEHOLDER);
		await user.click(input);
		await user.tab();

		await waitFor(() => {
			expect(
				screen.getByText("At least one tag is required"),
			).toBeInTheDocument();
		});
	});

	it("shows validation error on submit with empty tags", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		await user.click(screen.getByText("Submit"));

		await waitFor(() => {
			expect(
				screen.getByText("At least one tag is required"),
			).toBeInTheDocument();
		});
	});

	it("enforces maxItems limit", async () => {
		const user = userEvent.setup();
		render(<TestForm maxItems={2} defaultValues={["React"]} />);

		const input = screen.getByRole("textbox");
		await user.type(input, "TypeScript{Enter}");
		expect(screen.getByText("TypeScript")).toBeInTheDocument();

		// Input should now be hidden (at capacity)
		expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
		expect(screen.getByText("React")).toBeInTheDocument();
	});

	it("hides input when maxItems is reached", () => {
		render(<TestForm maxItems={2} defaultValues={["React", "TypeScript"]} />);
		expect(
			screen.queryByPlaceholderText(TAG_PLACEHOLDER),
		).not.toBeInTheDocument();
	});

	it("focuses input when clicking the container", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		const container = screen
			.getByPlaceholderText(TAG_PLACEHOLDER)
			.closest("[data-slot='tag-input-area']");
		await user.click(container as HTMLElement);

		expect(screen.getByPlaceholderText(TAG_PLACEHOLDER)).toHaveFocus();
	});

	it("does not submit the form on Enter key", async () => {
		const user = userEvent.setup();
		render(<TestForm />);

		const input = screen.getByPlaceholderText(TAG_PLACEHOLDER);
		await user.type(input, "React{Enter}");

		expect(screen.getByText("React")).toBeInTheDocument();
		expect(
			screen.queryByText("At least one tag is required"),
		).not.toBeInTheDocument();
	});
});
