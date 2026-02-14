"use client";

/**
 * Job detail page route.
 *
 * REQ-012 §8.3: Displays job metadata, scores, description,
 * ghost detection, and actions for a single job posting.
 */

import { useParams } from "next/navigation";

import { JobDetailHeader } from "@/components/jobs/job-detail-header";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function JobDetailPage() {
	const personaStatus = usePersonaStatus();
	const params = useParams<{ id: string }>();

	if (personaStatus.status !== "onboarded") return null;

	return (
		<div className="mx-auto max-w-4xl px-4 py-6">
			<JobDetailHeader jobId={params.id} />
		</div>
	);
}
