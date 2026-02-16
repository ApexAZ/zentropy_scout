/**
 * Culture signals display with quoted italic style.
 *
 * REQ-012 §8.3: Culture text section in job detail body.
 */

import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CultureSignalsProps {
	/** Extracted culture language. Null when not available. */
	cultureText: string | null;
	/** Additional CSS classes. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Renders culture signals as a quoted italic paragraph, or a "not available" badge. */
function CultureSignals({
	cultureText,
	className,
}: Readonly<CultureSignalsProps>) {
	if (cultureText === null) {
		return (
			<section
				data-testid="culture-signals"
				className={cn("flex items-center gap-2", className)}
			>
				<span className="text-sm font-semibold">Culture Signals:</span>
				<span
					data-testid="culture-not-available"
					className="border-border text-muted-foreground inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium"
				>
					No culture signals
				</span>
			</section>
		);
	}

	return (
		<section
			data-testid="culture-signals"
			className={cn("flex flex-col gap-2", className)}
		>
			<h3 className="text-sm font-semibold">Culture Signals</h3>
			<p
				data-testid="culture-text"
				className="text-muted-foreground text-sm italic"
			>
				{"\u201C"}
				{cultureText}
				{"\u201D"}
			</p>
		</section>
	);
}

export { CultureSignals };
export type { CultureSignalsProps };
