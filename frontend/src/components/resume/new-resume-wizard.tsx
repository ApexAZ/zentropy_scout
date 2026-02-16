"use client";

/**
 * New resume creation wizard with persona item selection.
 *
 * REQ-012 §9.2, §6.3.12: Form for creating a base resume —
 * name, role type, summary, hierarchical job/bullet checkboxes,
 * education/certification/skill selection, POST to /base-resumes.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

import { apiGet, apiPost } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { toFriendlyError } from "@/lib/form-errors";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { FailedState } from "@/components/ui/error-states";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type {
	Certification,
	Education,
	Skill,
	WorkHistory,
} from "@/types/persona";
import type { BaseResume } from "@/types/resume";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_NAME_LENGTH = 100;
const MAX_ROLE_TYPE_LENGTH = 255;
const MAX_SUMMARY_LENGTH = 5000;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NewResumeWizardProps {
	personaId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function NewResumeWizard({ personaId }: Readonly<NewResumeWizardProps>) {
	const router = useRouter();
	const queryClient = useQueryClient();

	// -----------------------------------------------------------------------
	// Data fetching
	// -----------------------------------------------------------------------

	const {
		data: workHistoryData,
		isLoading: workHistoryLoading,
		error: workHistoryError,
	} = useQuery({
		queryKey: queryKeys.workHistory(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<WorkHistory>>(
				`/personas/${personaId}/work-history`,
			),
	});

	const {
		data: educationData,
		isLoading: educationLoading,
		error: educationError,
	} = useQuery({
		queryKey: queryKeys.education(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<Education>>(`/personas/${personaId}/education`),
	});

	const {
		data: certificationData,
		isLoading: certificationLoading,
		error: certificationError,
	} = useQuery({
		queryKey: queryKeys.certifications(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<Certification>>(
				`/personas/${personaId}/certifications`,
			),
	});

	const {
		data: skillData,
		isLoading: skillLoading,
		error: skillError,
	} = useQuery({
		queryKey: queryKeys.skills(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<Skill>>(`/personas/${personaId}/skills`),
	});

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
	// Form state
	// -----------------------------------------------------------------------

	const [name, setName] = useState("");
	const [roleType, setRoleType] = useState("");
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
	const [isCreating, setIsCreating] = useState(false);
	const [defaultsInitialized, setDefaultsInitialized] = useState(false);

	// Default education and certifications to all selected (§6.3.12)
	useEffect(() => {
		if (!defaultsInitialized && educations.length > 0) {
			setIncludedEducation(educations.map((e) => e.id));
		}
	}, [defaultsInitialized, educations]);

	useEffect(() => {
		if (!defaultsInitialized && certifications.length > 0) {
			setIncludedCertifications(certifications.map((c) => c.id));
		}
	}, [defaultsInitialized, certifications]);

	// Mark defaults as initialized once data has arrived
	useEffect(() => {
		if (
			!defaultsInitialized &&
			educations.length > 0 &&
			certifications.length > 0
		) {
			setDefaultsInitialized(true);
		}
	}, [defaultsInitialized, educations, certifications]);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleToggleJob = useCallback((jobId: string, job: WorkHistory) => {
		setIncludedJobs((prev) => {
			if (prev.includes(jobId)) {
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

	const canSubmit =
		name.trim().length > 0 &&
		roleType.trim().length > 0 &&
		summary.trim().length > 0 &&
		!isCreating;

	const handleCreate = useCallback(async () => {
		if (!canSubmit) return;
		setIsCreating(true);
		try {
			const response = await apiPost<ApiResponse<BaseResume>>("/base-resumes", {
				persona_id: personaId,
				name: name.trim(),
				role_type: roleType.trim(),
				summary: summary.trim(),
				included_jobs: includedJobs,
				included_education: includedEducation,
				included_certifications: includedCertifications,
				skills_emphasis: skillsEmphasis,
				job_bullet_selections: bulletSelections,
				job_bullet_order: bulletOrder,
			});
			showToast.success("Resume created.");
			await queryClient.invalidateQueries({
				queryKey: queryKeys.baseResumes,
			});
			router.push(`/resumes/${response.data.id}`);
		} catch (err) {
			showToast.error(toFriendlyError(err));
		} finally {
			setIsCreating(false);
		}
	}, [
		canSubmit,
		personaId,
		name,
		roleType,
		summary,
		includedJobs,
		includedEducation,
		includedCertifications,
		skillsEmphasis,
		bulletSelections,
		bulletOrder,
		queryClient,
		router,
	]);

	// -----------------------------------------------------------------------
	// Loading / Error states
	// -----------------------------------------------------------------------

	const isLoading =
		workHistoryLoading ||
		educationLoading ||
		certificationLoading ||
		skillLoading;

	const error =
		workHistoryError ?? educationError ?? certificationError ?? skillError;

	if (isLoading) {
		return (
			<div data-testid="loading-spinner" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (error) {
		return <FailedState />;
	}

	// -----------------------------------------------------------------------
	// Main render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="new-resume-wizard">
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
				<h1 className="text-2xl font-bold">New Resume</h1>
			</div>

			{/* Name */}
			<div className="mb-6">
				<label htmlFor="resume-name" className="mb-2 block text-sm font-medium">
					Name
				</label>
				<input
					id="resume-name"
					type="text"
					value={name}
					onChange={(e) => setName(e.target.value)}
					maxLength={MAX_NAME_LENGTH}
					placeholder="e.g. Scrum Master"
					className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm"
				/>
			</div>

			{/* Role Type */}
			<div className="mb-6">
				<label
					htmlFor="resume-role-type"
					className="mb-2 block text-sm font-medium"
				>
					Role Type
				</label>
				<input
					id="resume-role-type"
					type="text"
					value={roleType}
					onChange={(e) => setRoleType(e.target.value)}
					maxLength={MAX_ROLE_TYPE_LENGTH}
					placeholder="e.g. Scrum Master roles"
					className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm"
				/>
			</div>

			{/* Summary */}
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
					placeholder="Professional summary for this resume..."
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

			{/* Submit */}
			<div className="flex items-center gap-2">
				<Button onClick={handleCreate} disabled={!canSubmit}>
					{isCreating ? (
						<>
							<Loader2 className="mr-1 h-4 w-4 animate-spin" />
							Creating...
						</>
					) : (
						"Create Resume"
					)}
				</Button>
			</div>
		</div>
	);
}
