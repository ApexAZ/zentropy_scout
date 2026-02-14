/**
 * Full job description text display.
 *
 * REQ-012 §8.3: Description section in job detail body.
 */

import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface JobDescriptionProps {
	/** Full job description text from the posting. */
	description: string;
	/** Additional CSS classes. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Renders the full job posting description with preserved whitespace. */
function JobDescription({ description, className }: JobDescriptionProps) {
	return (
		<section
			data-testid="job-description"
			className={cn("flex flex-col gap-2", className)}
		>
			<h3 className="text-sm font-semibold">Description</h3>
			<p
				data-testid="description-text"
				className="text-muted-foreground text-sm whitespace-pre-line"
			>
				{description}
			</p>
		</section>
	);
}

export { JobDescription };
export type { JobDescriptionProps };
