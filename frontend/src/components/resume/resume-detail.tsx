"use client";

/**
 * Resume detail page: summary editor, job/bullet reordering,
 * and education/certification/skill checkboxes.
 *
 * REQ-012 §9.2: Base resume editor with editable summary textarea,
 * hierarchical job/bullet inclusion checkboxes, bullet drag-and-drop
 * reordering, education/certification/skill selection, and save via PATCH.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

import { apiGet, apiPatch, apiPost, buildUrl } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { orderBullets } from "@/lib/resume-helpers";
import { showToast } from "@/lib/toast";
import { useResumeContentSelection } from "@/hooks/use-resume-content-selection";
import { ResumeContentCheckboxes } from "@/components/resume/resume-content-checkboxes";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { FailedState } from "@/components/ui/error-states";
import { PdfViewer } from "@/components/ui/pdf-viewer";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { VariantsList } from "@/components/resume/variants-list";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type {
	Bullet,
	Certification,
	Education,
	Skill,
	WorkHistory,
} from "@/types/persona";
import type { BaseResume } from "@/types/resume";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

const MAX_SUMMARY_LENGTH = 5000;

interface ResumeDetailProps {
	resumeId: string;
	personaId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ResumeDetail({
	resumeId,
	personaId,
}: Readonly<ResumeDetailProps>) {
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

	const { data: educationData, isLoading: educationLoading } = useQuery({
		queryKey: queryKeys.education(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<Education>>(`/personas/${personaId}/education`),
	});

	const { data: certificationData, isLoading: certificationLoading } = useQuery(
		{
			queryKey: queryKeys.certifications(personaId),
			queryFn: () =>
				apiGet<ApiListResponse<Certification>>(
					`/personas/${personaId}/certifications`,
				),
		},
	);

	const { data: skillData, isLoading: skillLoading } = useQuery({
		queryKey: queryKeys.skills(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<Skill>>(`/personas/${personaId}/skills`),
	});

	const resume = resumeData?.data;
	const jobs = workHistoryData?.data ?? [];
	const educations = useMemo(
		() => educationData?.data ?? [],
		[educationData?.data],
	);
	const certifications = useMemo(
		() => certificationData?.data ?? [],
		[certificationData?.data],
	);
	const skills = useMemo(() => skillData?.data ?? [], [skillData?.data]);

	// -----------------------------------------------------------------------
	// Local editable state (initialized from server data)
	// -----------------------------------------------------------------------

	const [summary, setSummary] = useState("");
	const selection = useResumeContentSelection();
	const [isInitialized, setIsInitialized] = useState(false);
	const [isSaving, setIsSaving] = useState(false);
	const [isRendering, setIsRendering] = useState(false);

	useEffect(() => {
		if (resume && !isInitialized) {
			setSummary(resume.summary);
			selection.setIncludedJobs(resume.included_jobs);
			selection.setBulletSelections(resume.job_bullet_selections);
			selection.setBulletOrder(resume.job_bullet_order);
			selection.setIncludedEducation(
				resume.included_education ?? educations.map((e) => e.id),
			);
			selection.setIncludedCertifications(
				resume.included_certifications ?? certifications.map((c) => c.id),
			);
			selection.setSkillsEmphasis(resume.skills_emphasis ?? []);
			setIsInitialized(true);
		}
	}, [resume, isInitialized, educations, certifications, selection]);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleReorderBullets = useCallback(
		(jobId: string, reorderedBullets: Bullet[]) => {
			selection.setBulletOrder((prev) => ({
				...prev,
				[jobId]: reorderedBullets.map((b) => b.id),
			}));
		},
		[selection],
	);

	const handleSave = useCallback(async () => {
		setIsSaving(true);
		try {
			await apiPatch(`/base-resumes/${resumeId}`, {
				summary,
				included_jobs: selection.includedJobs,
				job_bullet_selections: selection.bulletSelections,
				job_bullet_order: selection.bulletOrder,
				included_education: selection.includedEducation,
				included_certifications: selection.includedCertifications,
				skills_emphasis: selection.skillsEmphasis,
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
	}, [resumeId, summary, selection, queryClient]);

	const handleRenderPdf = useCallback(async () => {
		setIsRendering(true);
		try {
			await apiPost(`/base-resumes/${resumeId}/render`);
			showToast.success("PDF rendered.");
			await queryClient.invalidateQueries({
				queryKey: queryKeys.baseResume(resumeId),
			});
		} catch {
			showToast.error("Failed to render PDF.");
		} finally {
			setIsRendering(false);
		}
	}, [resumeId, queryClient]);

	// -----------------------------------------------------------------------
	// Render states
	// -----------------------------------------------------------------------

	const isLoading =
		resumeLoading ||
		workHistoryLoading ||
		educationLoading ||
		certificationLoading ||
		skillLoading;

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

	const needsRender =
		!resume.rendered_at || resume.updated_at > resume.rendered_at;
	const renderButtonLabel = resume.rendered_at ? "Re-render PDF" : "Render PDF";
	const downloadUrl = buildUrl(`/base-resumes/${resumeId}/download`);

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
				<div className="flex items-center gap-2">
					<h1 className="text-2xl font-bold">{resume.name}</h1>
					<span
						aria-label={`Status: ${resume.status}`}
						className="bg-muted rounded px-2 py-0.5 text-xs font-medium"
					>
						{resume.status}
					</span>
				</div>
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
					maxLength={MAX_SUMMARY_LENGTH}
					className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm"
				/>
			</div>

			{/* Content selection checkboxes */}
			<ResumeContentCheckboxes
				jobs={jobs}
				educations={educations}
				certifications={certifications}
				skills={skills}
				includedJobs={selection.includedJobs}
				bulletSelections={selection.bulletSelections}
				includedEducation={selection.includedEducation}
				includedCertifications={selection.includedCertifications}
				skillsEmphasis={selection.skillsEmphasis}
				onToggleJob={selection.handleToggleJob}
				onToggleBullet={selection.handleToggleBullet}
				onToggleEducation={selection.handleToggleEducation}
				onToggleCertification={selection.handleToggleCertification}
				onToggleSkill={selection.handleToggleSkill}
				renderBullets={(job, selectedBullets) => (
					<div className="ml-6">
						<ReorderableList
							items={orderBullets(job.bullets, selection.bulletOrder[job.id])}
							onReorder={(reordered) => handleReorderBullets(job.id, reordered)}
							label={`Bullets for ${job.job_title}`}
							renderItem={(bullet, dragHandle) => (
								<div className="flex items-center gap-2">
									{dragHandle}
									<Checkbox
										id={`bullet-${bullet.id}`}
										checked={selectedBullets.includes(bullet.id)}
										onCheckedChange={() =>
											selection.handleToggleBullet(job.id, bullet.id)
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
							)}
						/>
					</div>
				)}
			/>

			{/* Actions */}
			<div className="flex items-center gap-2">
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
				{needsRender && (
					<Button
						variant="outline"
						onClick={handleRenderPdf}
						disabled={isRendering}
					>
						{isRendering ? (
							<>
								<Loader2 className="mr-1 h-4 w-4 animate-spin" />
								Rendering...
							</>
						) : (
							renderButtonLabel
						)}
					</Button>
				)}
			</div>

			{/* PDF preview */}
			{resume.rendered_at && (
				<div className="mt-8">
					<h2 className="mb-4 text-lg font-semibold">PDF Preview</h2>
					<div className="h-[600px] rounded-md border">
						<PdfViewer src={downloadUrl} fileName={`${resume.name}.pdf`} />
					</div>
				</div>
			)}

			{/* Job Variants */}
			<div className="mt-8">
				<VariantsList baseResumeId={resumeId} />
			</div>
		</div>
	);
}
