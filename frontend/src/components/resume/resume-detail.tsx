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

import { apiGet, apiPatch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { FailedState } from "@/components/ui/error-states";
import { ReorderableList } from "@/components/ui/reorderable-list";
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
// Helpers
// ---------------------------------------------------------------------------

/** Sort bullets according to a specified order. Unordered bullets go to end. */
function orderBullets(
	bullets: Bullet[],
	order: string[] | undefined,
): Bullet[] {
	if (!order || order.length === 0) return bullets;
	return [...bullets].sort((a, b) => {
		const aIdx = order.indexOf(a.id);
		const bIdx = order.indexOf(b.id);
		return (aIdx === -1 ? Infinity : aIdx) - (bIdx === -1 ? Infinity : bIdx);
	});
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
	const [includedJobs, setIncludedJobs] = useState<string[]>([]);
	const [bulletSelections, setBulletSelections] = useState<
		Record<string, string[]>
	>({});
	const [bulletOrder, setBulletOrder] = useState<Record<string, string[]>>({});
	const [includedEducation, setIncludedEducation] = useState<string[]>([]);
	const [includedCertifications, setIncludedCertifications] = useState<
		string[]
	>([]);
	const [skillsEmphasis, setSkillsEmphasis] = useState<string[]>([]);
	const [isInitialized, setIsInitialized] = useState(false);
	const [isSaving, setIsSaving] = useState(false);

	useEffect(() => {
		if (resume && !isInitialized) {
			setSummary(resume.summary);
			setIncludedJobs(resume.included_jobs);
			setBulletSelections(resume.job_bullet_selections);
			setBulletOrder(resume.job_bullet_order);
			setIncludedEducation(
				resume.included_education ?? educations.map((e) => e.id),
			);
			setIncludedCertifications(
				resume.included_certifications ?? certifications.map((c) => c.id),
			);
			setSkillsEmphasis(resume.skills_emphasis ?? []);
			setIsInitialized(true);
		}
	}, [resume, isInitialized, educations, certifications]);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleToggleJob = useCallback((jobId: string, job: WorkHistory) => {
		setIncludedJobs((prev) => {
			if (prev.includes(jobId)) {
				// Removing job — clear bullet selections and order
				setBulletSelections((bs) => {
					const next = { ...bs };
					delete next[jobId];
					return next;
				});
				setBulletOrder((bo) => {
					const next = { ...bo };
					delete next[jobId];
					return next;
				});
				return prev.filter((id) => id !== jobId);
			}
			// Adding job — select all bullets and set initial order
			const allBulletIds = job.bullets.map((b) => b.id);
			setBulletSelections((bs) => ({
				...bs,
				[jobId]: allBulletIds,
			}));
			setBulletOrder((bo) => ({
				...bo,
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

	const handleReorderBullets = useCallback(
		(jobId: string, reorderedBullets: Bullet[]) => {
			setBulletOrder((prev) => ({
				...prev,
				[jobId]: reorderedBullets.map((b) => b.id),
			}));
		},
		[],
	);

	const handleToggleEducation = useCallback((eduId: string) => {
		setIncludedEducation((prev) =>
			prev.includes(eduId)
				? prev.filter((id) => id !== eduId)
				: [...prev, eduId],
		);
	}, []);

	const handleToggleCertification = useCallback((certId: string) => {
		setIncludedCertifications((prev) =>
			prev.includes(certId)
				? prev.filter((id) => id !== certId)
				: [...prev, certId],
		);
	}, []);

	const handleToggleSkill = useCallback((skillId: string) => {
		setSkillsEmphasis((prev) =>
			prev.includes(skillId)
				? prev.filter((id) => id !== skillId)
				: [...prev, skillId],
		);
	}, []);

	const handleSave = useCallback(async () => {
		setIsSaving(true);
		try {
			await apiPatch(`/base-resumes/${resumeId}`, {
				summary,
				included_jobs: includedJobs,
				job_bullet_selections: bulletSelections,
				job_bullet_order: bulletOrder,
				included_education: includedEducation,
				included_certifications: includedCertifications,
				skills_emphasis: skillsEmphasis,
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
	}, [
		resumeId,
		summary,
		includedJobs,
		bulletSelections,
		bulletOrder,
		includedEducation,
		includedCertifications,
		skillsEmphasis,
		queryClient,
	]);

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
					maxLength={MAX_SUMMARY_LENGTH}
					className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm"
				/>
			</div>

			{/* Job inclusion checkboxes with reorderable bullets */}
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

								{/* Bullet-level checkboxes with drag-and-drop reordering */}
								{isIncluded && job.bullets.length > 0 && (
									<div className="ml-6">
										<ReorderableList
											items={orderBullets(job.bullets, bulletOrder[job.id])}
											onReorder={(reordered) =>
												handleReorderBullets(job.id, reordered)
											}
											label={`Bullets for ${job.job_title}`}
											renderItem={(bullet, dragHandle) => (
												<div className="flex items-center gap-2">
													{dragHandle}
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
											)}
										/>
									</div>
								)}
							</div>
						);
					})}
				</div>
			</div>

			{/* Education checkboxes */}
			{educations.length > 0 && (
				<div className="mb-8">
					<h2 className="mb-4 text-lg font-semibold">Education</h2>
					<div className="space-y-2">
						{educations.map((edu) => (
							<div key={edu.id} className="flex items-center gap-2">
								<Checkbox
									id={`education-${edu.id}`}
									checked={includedEducation.includes(edu.id)}
									onCheckedChange={() => handleToggleEducation(edu.id)}
									aria-label={`${edu.degree} ${edu.field_of_study} at ${edu.institution}`}
								/>
								<label
									htmlFor={`education-${edu.id}`}
									className="cursor-pointer text-sm"
								>
									{edu.degree} {edu.field_of_study} &mdash; {edu.institution}
								</label>
							</div>
						))}
					</div>
				</div>
			)}

			{/* Certification checkboxes */}
			{certifications.length > 0 && (
				<div className="mb-8">
					<h2 className="mb-4 text-lg font-semibold">Certifications</h2>
					<div className="space-y-2">
						{certifications.map((cert) => (
							<div key={cert.id} className="flex items-center gap-2">
								<Checkbox
									id={`certification-${cert.id}`}
									checked={includedCertifications.includes(cert.id)}
									onCheckedChange={() => handleToggleCertification(cert.id)}
									aria-label={`${cert.certification_name} from ${cert.issuing_organization}`}
								/>
								<label
									htmlFor={`certification-${cert.id}`}
									className="cursor-pointer text-sm"
								>
									{cert.certification_name} &mdash; {cert.issuing_organization}
								</label>
							</div>
						))}
					</div>
				</div>
			)}

			{/* Skills emphasis checkboxes */}
			{skills.length > 0 && (
				<div className="mb-8">
					<h2 className="mb-4 text-lg font-semibold">Skills Emphasis</h2>
					<div className="flex flex-wrap gap-2">
						{skills.map((skill) => (
							<div
								key={skill.id}
								className="flex items-center gap-2 rounded-md border px-2 py-1"
							>
								<Checkbox
									id={`skill-${skill.id}`}
									checked={skillsEmphasis.includes(skill.id)}
									onCheckedChange={() => handleToggleSkill(skill.id)}
									aria-label={skill.skill_name}
								/>
								<label
									htmlFor={`skill-${skill.id}`}
									className="cursor-pointer text-sm"
								>
									{skill.skill_name}
								</label>
							</div>
						))}
					</div>
				</div>
			)}

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
