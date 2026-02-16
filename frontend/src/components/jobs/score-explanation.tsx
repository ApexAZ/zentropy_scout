/**
 * Score explanation display with summary and categorized icon lists.
 *
 * REQ-012 §8.3: Explanation section below score breakdowns.
 * REQ-008 §8.1: Summary paragraph + strengths, gaps, stretch, warnings.
 */

import { AlertTriangle, CheckCircle2, Info, TrendingUp } from "lucide-react";

import type { ScoreExplanation as ScoreExplanationType } from "@/types/job";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ScoreExplanationProps {
	/** Explanation data. Undefined when job has not been scored. */
	explanation: ScoreExplanationType | undefined;
	/** Additional CSS classes. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

interface CategoryConfig {
	testId: string;
	label: string;
	icon: React.ReactNode;
	items: string[];
}

function CategorySection({ testId, label, icon, items }: CategoryConfig) {
	if (items.length === 0) return null;

	return (
		<div data-testid={testId} className="space-y-1">
			<div className="flex items-center gap-2 text-sm font-medium">
				{icon}
				<span>{label}</span>
			</div>
			<ul className="ml-6 space-y-0.5">
				{items.map((item) => (
					<li key={item} className="text-muted-foreground text-sm">
						{item}
					</li>
				))}
			</ul>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Renders a structured score explanation with summary paragraph and
 * categorized icon lists for strengths, gaps, stretch opportunities,
 * and warnings.
 */
function ScoreExplanation({ explanation, className }: ScoreExplanationProps) {
	if (!explanation) {
		return (
			<section
				data-testid="score-explanation"
				className={cn("flex items-center gap-2", className)}
			>
				<span className="text-sm font-semibold">Explanation:</span>
				<span
					data-testid="explanation-not-available"
					className="border-border text-muted-foreground inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium"
				>
					No explanation
				</span>
			</section>
		);
	}

	return (
		<section
			data-testid="score-explanation"
			className={cn("flex flex-col gap-3", className)}
		>
			<h3 className="text-sm font-semibold">Explanation</h3>
			<p data-testid="explanation-summary" className="text-sm">
				{explanation.summary}
			</p>

			<CategorySection
				testId="explanation-strengths"
				label="Strengths"
				icon={<CheckCircle2 className="h-4 w-4 text-green-500" />}
				items={explanation.strengths}
			/>
			<CategorySection
				testId="explanation-gaps"
				label="Gaps"
				icon={<AlertTriangle className="h-4 w-4 text-amber-500" />}
				items={explanation.gaps}
			/>
			<CategorySection
				testId="explanation-stretch"
				label="Stretch Opportunities"
				icon={<TrendingUp className="h-4 w-4 text-purple-500" />}
				items={explanation.stretch_opportunities}
			/>
			<CategorySection
				testId="explanation-warnings"
				label="Warnings"
				icon={<Info className="h-4 w-4 text-blue-500" />}
				items={explanation.warnings}
			/>
		</section>
	);
}

export { ScoreExplanation };
export type { ScoreExplanationProps };
