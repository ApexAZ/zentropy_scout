"use client";

/**
 * Resume detail page: summary editor and job inclusion checkboxes.
 *
 * REQ-012 §9.2: Base resume editor with editable summary textarea,
 * hierarchical job/bullet inclusion checkboxes, and save via PATCH.
 */

import { useCallback, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

import { apiGet, apiPatch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { FailedState } from "@/components/ui/error-states";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { WorkHistory } from "@/types/persona";
import type { BaseResume } from "@/types/resume";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ResumeDetailProps {
	resumeId: string;
	personaId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ResumeDetail({ resumeId, personaId }: ResumeDetailProps) {
	const queryClient = useQueryClient();

	// -----------------------------------------------------------------------
	// Data fetching
	// -----------------------------------------------------------------------

	const {
		data: resumeData,
		isLoading: resumeLoading,
		error: resumeError,
		refetch: refetchResume,
	} = useQuery({
		queryKey: queryKeys.baseResume(resumeId),
		queryFn: () => apiGet<ApiResponse<BaseResume>>(`/base-resumes/${resumeId}`),
	});

	const { data: workHistoryData, isLoading: workHistoryLoading } = useQuery({
		queryKey: queryKeys.workHistory(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<WorkHistory>>(
				`/personas/${personaId}/work-history`,
			),
	});

	const resume = resumeData?.data;
	const jobs = workHistoryData?.data ?? [];

	// -----------------------------------------------------------------------
	// Local editable state (initialized from server data)
	// -----------------------------------------------------------------------

	const [summary, setSummary] = useState("");
	const [includedJobs, setIncludedJobs] = useState<string[]>([]);
	const [bulletSelections, setBulletSelections] = useState<
		Record<string, string[]>
	>({});
	const [isInitialized, setIsInitialized] = useState(false);
	const [isSaving, setIsSaving] = useState(false);

	useEffect(() => {
		if (resume && !isInitialized) {
			setSummary(resume.summary);
			setIncludedJobs(resume.included_jobs);
			setBulletSelections(resume.job_bullet_selections);
			setIsInitialized(true);
		}
	}, [resume, isInitialized]);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleToggleJob = useCallback((jobId: string, job: WorkHistory) => {
		setIncludedJobs((prev) => {
			if (prev.includes(jobId)) {
				// Removing job — also clear its bullet selections
				setBulletSelections((bs) => {
					const next = { ...bs };
					delete next[jobId];
					return next;
				});
				return prev.filter((id) => id !== jobId);
			}
			// Adding job — select all bullets by default
			const allBulletIds = job.bullets.map((b) => b.id);
			setBulletSelections((bs) => ({
				...bs,
				[jobId]: allBulletIds,
			}));
			return [...prev, jobId];
		});
	}, []);

	const handleToggleBullet = useCallback((jobId: string, bulletId: string) => {
		setBulletSelections((prev) => {
			const current = prev[jobId] ?? [];
			const next = current.includes(bulletId)
				? current.filter((id) => id !== bulletId)
				: [...current, bulletId];
			return { ...prev, [jobId]: next };
		});
	}, []);

	const handleSave = useCallback(async () => {
		setIsSaving(true);
		try {
			await apiPatch(`/base-resumes/${resumeId}`, {
				summary,
				included_jobs: includedJobs,
				job_bullet_selections: bulletSelections,
			});
			showToast.success("Resume saved.");
			await queryClient.invalidateQueries({
				queryKey: queryKeys.baseResume(resumeId),
			});
		} catch {
			showToast.error("Failed to save resume.");
		} finally {
			setIsSaving(false);
		}
	}, [resumeId, summary, includedJobs, bulletSelections, queryClient]);

	// -----------------------------------------------------------------------
	// Render states
	// -----------------------------------------------------------------------

	const isLoading = resumeLoading || workHistoryLoading;

	if (isLoading) {
		return (
			<div data-testid="loading-spinner" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (resumeError) {
		return <FailedState onRetry={() => refetchResume()} />;
	}

	if (!resume) return null;

	// -----------------------------------------------------------------------
	// Main render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="resume-detail">
			{/* Header */}
			<div className="mb-6">
				<Link
					href="/resumes"
					aria-label="Back to Resumes"
					className="text-muted-foreground hover:text-foreground mb-2 inline-flex items-center gap-1 text-sm"
				>
					<ArrowLeft className="h-4 w-4" />
					Back to Resumes
				</Link>
				<h1 className="text-2xl font-bold">{resume.name}</h1>
				<p className="text-muted-foreground text-sm">{resume.role_type}</p>
			</div>

			{/* Summary editor */}
			<div className="mb-8">
				<label
					htmlFor="resume-summary"
					className="mb-2 block text-sm font-medium"
				>
					Summary
				</label>
				<textarea
					id="resume-summary"
					value={summary}
					onChange={(e) => setSummary(e.target.value)}
					rows={5}
					maxLength={5000}
					className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm"
				/>
			</div>

			{/* Job inclusion checkboxes */}
			<div className="mb-8">
				<h2 className="mb-4 text-lg font-semibold">Included Jobs</h2>
				<div className="space-y-4">
					{jobs.map((job) => {
						const isIncluded = includedJobs.includes(job.id);
						const selectedBullets = bulletSelections[job.id] ?? [];

						return (
							<div key={job.id} className="space-y-2">
								{/* Job-level checkbox */}
								<div className="flex items-center gap-2">
									<Checkbox
										id={`job-${job.id}`}
										checked={isIncluded}
										onCheckedChange={() => handleToggleJob(job.id, job)}
										aria-label={`${job.job_title} at ${job.company_name}`}
									/>
									<label
										htmlFor={`job-${job.id}`}
										className="cursor-pointer text-sm font-medium"
									>
										{job.job_title}
									</label>
									<span className="text-muted-foreground text-sm">
										{job.company_name}
									</span>
								</div>

								{/* Bullet-level checkboxes (shown only for included jobs) */}
								{isIncluded && job.bullets.length > 0 && (
									<div className="ml-6 space-y-1">
										{job.bullets.map((bullet) => (
											<div key={bullet.id} className="flex items-center gap-2">
												<Checkbox
													id={`bullet-${bullet.id}`}
													checked={selectedBullets.includes(bullet.id)}
													onCheckedChange={() =>
														handleToggleBullet(job.id, bullet.id)
													}
													aria-label={bullet.text}
												/>
												<label
													htmlFor={`bullet-${bullet.id}`}
													className="text-muted-foreground cursor-pointer text-sm"
												>
													{bullet.text}
												</label>
											</div>
										))}
									</div>
								)}
							</div>
						);
					})}
				</div>
			</div>

			{/* Save button */}
			<Button onClick={handleSave} disabled={isSaving}>
				{isSaving ? (
					<>
						<Loader2 className="mr-1 h-4 w-4 animate-spin" />
						Saving...
					</>
				) : (
					"Save"
				)}
			</Button>
		</div>
	);
}
