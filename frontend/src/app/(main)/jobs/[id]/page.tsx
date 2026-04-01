"use client";

/**
 * @fileoverview Job detail page with scores, description, and actions.
 *
 * Layer: page
 * Feature: jobs
 *
 * REQ-012 §8.3: Displays job metadata, scores, description,
 * ghost detection, and actions for a single job posting.
 * REQ-015 §8: Uses PersonaJobResponse (nested shared + per-user).
 *
 * Coordinates with:
 * - lib/api-client.ts: apiGet for job and extracted skills fetches
 * - lib/query-keys.ts: queryKeys.job, queryKeys.extractedSkills
 * - hooks/use-persona-status.ts: persona status check for guard
 * - components/jobs/job-detail-header.tsx, job-detail-actions.tsx: header and actions
 * - components/jobs/score-breakdown.tsx, score-explanation.tsx: scoring display
 * - components/jobs/job-description.tsx, culture-signals.tsx, extracted-skills-tags.tsx: posting content
 * - components/jobs/cover-letter-section.tsx, create-variant-card.tsx: materials generation
 * - components/jobs/draft-materials-card.tsx, review-materials-link.tsx: materials navigation
 * - components/jobs/mark-as-applied-card.tsx: application tracking action
 * - types/api.ts: ApiResponse, ApiListResponse envelope types
 * - types/job.ts: PersonaJobResponse, ExtractedSkill types
 *
 * Called by / Used by:
 * - Next.js framework: route /jobs/[id]
 */

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { CoverLetterSection } from "@/components/jobs/cover-letter-section";
import { CreateVariantCard } from "@/components/jobs/create-variant-card";
import { DraftMaterialsCard } from "@/components/jobs/draft-materials-card";
import { ReviewMaterialsLink } from "@/components/jobs/review-materials-link";
import { CultureSignals } from "@/components/jobs/culture-signals";
import { ExtractedSkillsTags } from "@/components/jobs/extracted-skills-tags";
import { JobDescription } from "@/components/jobs/job-description";
import { JobDetailActions } from "@/components/jobs/job-detail-actions";
import { JobDetailHeader } from "@/components/jobs/job-detail-header";
import { MarkAsAppliedCard } from "@/components/jobs/mark-as-applied-card";
import { ScoreBreakdown } from "@/components/jobs/score-breakdown";
import { ScoreExplanation } from "@/components/jobs/score-explanation";
import { usePersonaStatus } from "@/hooks/use-persona-status";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { ExtractedSkill, PersonaJobResponse } from "@/types/job";

/** Job detail page displaying metadata, scores, and posting details. */
export default function JobDetailPage() {
	const personaStatus = usePersonaStatus();
	const params = useParams<{ id: string }>();
	const isOnboarded = personaStatus.status === "onboarded";

	const { data } = useQuery({
		queryKey: queryKeys.job(params.id),
		queryFn: () =>
			apiGet<ApiResponse<PersonaJobResponse>>(`/job-postings/${params.id}`),
		enabled: isOnboarded,
	});

	const { data: skillsData } = useQuery({
		queryKey: queryKeys.extractedSkills(params.id),
		queryFn: () =>
			apiGet<ApiListResponse<ExtractedSkill>>(
				`/job-postings/${params.id}/extracted-skills`,
			),
		enabled: isOnboarded,
	});

	if (!isOnboarded) return null;

	const personaJob = data?.data;

	return (
		<div className="mx-auto max-w-4xl px-4 py-6">
			<JobDetailHeader jobId={params.id} />
			{personaJob && (
				<>
					<div className="mt-4">
						<JobDetailActions
							personaJobId={personaJob.id}
							status={personaJob.status}
						/>
					</div>
					<div className="mt-6">
						<MarkAsAppliedCard
							jobId={params.id}
							applyUrl={personaJob.job.apply_url}
						/>
					</div>
					<div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
						<ScoreBreakdown
							score={personaJob.score_details?.fit}
							scoreType="fit"
						/>
						<ScoreBreakdown
							score={personaJob.score_details?.stretch}
							scoreType="stretch"
						/>
					</div>
					<ScoreExplanation
						explanation={personaJob.score_details?.explanation}
						className="mt-4"
					/>
					<div className="mt-6">
						<CoverLetterSection jobId={params.id} />
					</div>
					<div className="mt-6">
						<CreateVariantCard jobPostingId={personaJob.job.id} />
					</div>
					<div className="mt-6">
						<DraftMaterialsCard jobId={params.id} />
					</div>
					<div className="mt-6">
						<ReviewMaterialsLink jobId={params.id} />
					</div>
					<ExtractedSkillsTags skills={skillsData?.data} className="mt-4" />
					<JobDescription
						description={personaJob.job.description}
						className="mt-4"
					/>
					<CultureSignals
						cultureText={personaJob.job.culture_text}
						className="mt-4"
					/>
				</>
			)}
		</div>
	);
}
