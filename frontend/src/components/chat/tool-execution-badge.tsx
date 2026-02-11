/**
 * Inline badge for tool execution status during chat streaming.
 *
 * REQ-012 §5.4: On tool_start, show inline badge with spinner.
 * On tool_result, replace spinner with success (checkmark) or
 * failure (X) icon.
 */

import { Check, Loader2, X } from "lucide-react";

import type { ToolExecution, ToolExecutionStatus } from "@/types/chat";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Converts a snake_case tool name to a human-readable label.
 *
 * @example formatToolLabel("favorite_job") → "Favorite job"
 * @example formatToolLabel("generate_cover_letter") → "Generate cover letter"
 */
export function formatToolLabel(tool: string): string {
	const trimmed = tool.trim();
	if (trimmed === "") return "";
	const words = trimmed.split("_");
	return [
		words[0].charAt(0).toUpperCase() + words[0].slice(1),
		...words.slice(1),
	].join(" ");
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ToolExecutionBadgeProps {
	/** The tool execution to display. */
	execution: ToolExecution;
	/** Additional CSS classes. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ICON_SIZE = "h-3 w-3";

const STATUS_STYLES: Record<ToolExecutionStatus, string> = {
	running: "bg-muted text-muted-foreground",
	success: "bg-success/10 text-success",
	error: "bg-destructive/10 text-destructive",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Displays an inline badge/chip showing a tool execution status.
 *
 * - **running**: Spinner icon + tool label + "..."
 * - **success**: Checkmark icon + tool label
 * - **error**: X icon + tool label
 *
 * @param props.execution - The ToolExecution object with tool name and status.
 * @param props.className - Optional extra CSS classes.
 */
export function ToolExecutionBadge({
	execution,
	className,
}: ToolExecutionBadgeProps) {
	const { tool, status } = execution;
	const label = formatToolLabel(tool);
	const isRunning = status === "running";

	return (
		<span
			data-slot="tool-execution"
			data-status={status}
			aria-label={`${label}: ${status}`}
			className={cn(
				"inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
				STATUS_STYLES[status],
				className,
			)}
		>
			{status === "running" && (
				<Loader2
					data-slot="tool-spinner"
					aria-hidden="true"
					className={cn(ICON_SIZE, "motion-safe:animate-spin")}
				/>
			)}
			{status === "success" && (
				<Check
					data-slot="tool-success-icon"
					aria-hidden="true"
					className={ICON_SIZE}
				/>
			)}
			{status === "error" && (
				<X
					data-slot="tool-error-icon"
					aria-hidden="true"
					className={ICON_SIZE}
				/>
			)}
			{label}
			{isRunning && "..."}
		</span>
	);
}
