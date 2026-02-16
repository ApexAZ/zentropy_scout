/**
 * Grouped skill tag chips for extracted job skills.
 *
 * REQ-012 §8.3: Extracted skills display with Required / Preferred grouping.
 * REQ-005 §4.2: ExtractedSkill model shape.
 */

import type { ExtractedSkill } from "@/types/job";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ExtractedSkillsTagsProps {
	/** Extracted skills from the job posting. Undefined when not yet loaded. */
	skills: ExtractedSkill[] | undefined;
	/** Additional CSS classes. */
	className?: string;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function SkillChip({
	skill,
	variant,
}: Readonly<{
	skill: ExtractedSkill;
	variant: "required" | "preferred";
}>) {
	const label =
		skill.years_requested === null
			? skill.skill_name
			: `${skill.skill_name} (${skill.years_requested}+ yr)`;

	return (
		<span
			data-testid={`skill-chip-${skill.id}`}
			className={cn(
				"inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
				variant === "required"
					? "border-primary/20 bg-primary/10 text-primary"
					: "border-border text-muted-foreground",
			)}
		>
			{label}
		</span>
	);
}

function SkillGroup({
	testId,
	label,
	skills,
	variant,
}: Readonly<{
	testId: string;
	label: string;
	skills: ExtractedSkill[];
	variant: "required" | "preferred";
}>) {
	if (skills.length === 0) return null;

	return (
		<div data-testid={testId} className="space-y-1.5">
			<span className="text-muted-foreground text-xs font-medium">{label}</span>
			<div className="flex flex-wrap gap-1.5">
				{skills.map((skill) => (
					<SkillChip key={skill.id} skill={skill} variant={variant} />
				))}
			</div>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Renders extracted job skills as grouped tag chips (Required / Preferred). */
function ExtractedSkillsTags({
	skills,
	className,
}: Readonly<ExtractedSkillsTagsProps>) {
	const hasSkills = skills && skills.length > 0;

	if (!hasSkills) {
		return (
			<section
				data-testid="extracted-skills-tags"
				className={cn("flex items-center gap-2", className)}
			>
				<span className="text-sm font-semibold">Extracted Skills:</span>
				<span
					data-testid="skills-not-available"
					className="border-border text-muted-foreground inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium"
				>
					No skills extracted
				</span>
			</section>
		);
	}

	const required = skills.filter((s) => s.is_required);
	const preferred = skills.filter((s) => !s.is_required);

	return (
		<section
			data-testid="extracted-skills-tags"
			className={cn("flex flex-col gap-3", className)}
		>
			<h3 className="text-sm font-semibold">Extracted Skills</h3>
			<SkillGroup
				testId="skills-required-group"
				label="Required"
				skills={required}
				variant="required"
			/>
			<SkillGroup
				testId="skills-preferred-group"
				label="Preferred"
				skills={preferred}
				variant="preferred"
			/>
		</section>
	);
}

export { ExtractedSkillsTags };
export type { ExtractedSkillsTagsProps };
