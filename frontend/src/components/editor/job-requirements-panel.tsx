/**
 * Job requirements panel for the variant editor.
 *
 * REQ-027 §4.4: Shows job posting key skills, fit score, and
 * requirements context when editing a job variant.
 */

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { apiGet } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { ScoreTierBadge } from "@/components/ui/score-tier-badge";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { ExtractedSkill, PersonaJobResponse } from "@/types/job";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface JobRequirementsPanelProps {
	jobPostingId: string;
}

// ---------------------------------------------------------------------------
// Sub-components
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
			className={
				variant === "required"
					? "border-primary/20 bg-primary/10 text-primary inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium"
					: "border-border text-muted-foreground inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium"
			}
		>
			{label}
		</span>
	);
}

function SkillGroup({
	label,
	skills,
	variant,
}: Readonly<{
	label: string;
	skills: ExtractedSkill[];
	variant: "required" | "preferred";
}>) {
	if (skills.length === 0) return null;

	return (
		<div className="space-y-1.5">
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

export function JobRequirementsPanel({
	jobPostingId,
}: Readonly<JobRequirementsPanelProps>) {
	const { data: jobData, isLoading: jobLoading } = useQuery({
		queryKey: queryKeys.job(jobPostingId),
		queryFn: () =>
			apiGet<ApiResponse<PersonaJobResponse>>(`/job-postings/${jobPostingId}`),
	});

	const { data: skillsData, isLoading: skillsLoading } = useQuery({
		queryKey: queryKeys.extractedSkills(jobPostingId),
		queryFn: () =>
			apiGet<ApiListResponse<ExtractedSkill>>(
				`/job-postings/${jobPostingId}/extracted-skills`,
			),
	});

	const isLoading = jobLoading || skillsLoading;

	if (isLoading) {
		return (
			<div
				data-testid="job-requirements-loading"
				className="flex items-center justify-center py-8"
			>
				<Loader2 className="text-muted-foreground h-5 w-5 animate-spin" />
			</div>
		);
	}

	const personaJob = jobData?.data;
	const job = personaJob?.job;
	const skills = skillsData?.data ?? [];
	const required = skills.filter((s) => s.is_required);
	const preferred = skills.filter((s) => !s.is_required);
	const hasSkills = skills.length > 0;

	return (
		<div
			data-testid="job-requirements-panel"
			className="space-y-3 overflow-y-auto text-sm"
		>
			<h3 className="px-1 text-xs font-semibold tracking-wide uppercase">
				Job Requirements
			</h3>

			{/* Job title + company */}
			{job && (
				<div className="space-y-0.5 px-1">
					<p className="font-medium">{job.job_title}</p>
					<p className="text-muted-foreground text-xs">at {job.company_name}</p>
				</div>
			)}

			{/* Fit score */}
			{personaJob && (
				<div className="flex items-center gap-2 px-1">
					<span className="text-muted-foreground text-xs">Fit:</span>
					<ScoreTierBadge score={personaJob.fit_score} scoreType="fit" />
				</div>
			)}

			{/* Key skills */}
			<div className="space-y-2 px-1">
				{hasSkills ? (
					<>
						<SkillGroup label="Required" skills={required} variant="required" />
						<SkillGroup
							label="Preferred"
							skills={preferred}
							variant="preferred"
						/>
					</>
				) : (
					<p className="text-muted-foreground text-xs italic">
						No skills extracted
					</p>
				)}
			</div>

			{/* Requirements text */}
			{job?.requirements && (
				<div className="space-y-1 px-1">
					<span className="text-muted-foreground text-xs font-medium">
						Requirements
					</span>
					<p className="text-muted-foreground text-xs leading-relaxed">
						{job.requirements}
					</p>
				</div>
			)}
		</div>
	);
}
