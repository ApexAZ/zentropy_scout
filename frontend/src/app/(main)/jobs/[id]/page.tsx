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
import { FitScoreBreakdown } from "@/components/jobs/fit-score-breakdown";
import { JobDetailHeader } from "@/components/jobs/job-detail-header";
import { usePersonaStatus } from "@/hooks/use-persona-status";
import type { ApiResponse } from "@/types/api";
import type { JobPosting } from "@/types/job";

export default function JobDetailPage() {
	const personaStatus = usePersonaStatus();
	const params = useParams<{ id: string }>();

	const { data } = useQuery({
		queryKey: queryKeys.job(params.id),
		queryFn: () =>
			apiGet<ApiResponse<JobPosting>>(`/job-postings/${params.id}`),
		enabled: personaStatus.status === "onboarded",
	});

	if (personaStatus.status !== "onboarded") return null;

	const job = data?.data;

	return (
		<div className="mx-auto max-w-4xl px-4 py-6">
			<JobDetailHeader jobId={params.id} />
			{job && (
				<FitScoreBreakdown fit={job.score_details?.fit} className="mt-6" />
			)}
		</div>
	);
}
