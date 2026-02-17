"use client";

/**
 * Job detail page route.
 *
 * REQ-012 §8.3: Displays job metadata, scores, description,
 * ghost detection, and actions for a single job posting.
 */

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { CultureSignals } from "@/components/jobs/culture-signals";
import { ExtractedSkillsTags } from "@/components/jobs/extracted-skills-tags";
import { JobDescription } from "@/components/jobs/job-description";
import { JobDetailHeader } from "@/components/jobs/job-detail-header";
import { MarkAsAppliedCard } from "@/components/jobs/mark-as-applied-card";
import { ScoreBreakdown } from "@/components/jobs/score-breakdown";
import { ScoreExplanation } from "@/components/jobs/score-explanation";
import { usePersonaStatus } from "@/hooks/use-persona-status";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { ExtractedSkill, JobPosting } from "@/types/job";

/** Job detail page displaying metadata, scores, and posting details. */
export default function JobDetailPage() {
	const personaStatus = usePersonaStatus();
	const params = useParams<{ id: string }>();
	const isOnboarded = personaStatus.status === "onboarded";

	const { data } = useQuery({
		queryKey: queryKeys.job(params.id),
		queryFn: () =>
			apiGet<ApiResponse<JobPosting>>(`/job-postings/${params.id}`),
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

	const job = data?.data;

	return (
		<div className="mx-auto max-w-4xl px-4 py-6">
			<JobDetailHeader jobId={params.id} />
			{job && (
				<>
					<div className="mt-6">
						<MarkAsAppliedCard jobId={params.id} applyUrl={job.apply_url} />
					</div>
					<div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
						<ScoreBreakdown score={job.score_details?.fit} scoreType="fit" />
						<ScoreBreakdown
							score={job.score_details?.stretch}
							scoreType="stretch"
						/>
					</div>
					<ScoreExplanation
						explanation={job.score_details?.explanation}
						className="mt-4"
					/>
					<ExtractedSkillsTags skills={skillsData?.data} className="mt-4" />
					<JobDescription description={job.description} className="mt-4" />
					<CultureSignals cultureText={job.culture_text} className="mt-4" />
				</>
			)}
		</div>
	);
}
