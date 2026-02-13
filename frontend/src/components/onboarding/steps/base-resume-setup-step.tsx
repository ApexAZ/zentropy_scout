"use client";

/**
 * Base resume setup step for onboarding wizard (Step 12).
 *
 * REQ-012 §6.3.12: Resume creation form with item selection checkboxes.
 * User enters resume name, role type, and summary, then selects which
 * work history entries (with bullets), education, certifications, and
 * skills to include. All items are checked by default. POST creates
 * the base resume and completes onboarding.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { FormErrorSummary } from "@/components/form/form-error-summary";
import { FormInputField } from "@/components/form/form-input-field";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Textarea } from "@/components/ui/textarea";
import { apiGet, apiPost } from "@/lib/api-client";
import { useChat } from "@/lib/chat-provider";
import { toFriendlyError } from "@/lib/form-errors";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { ApiListResponse } from "@/types/api";
import type {
	Certification,
	Education,
	Skill,
	WorkHistory,
} from "@/types/persona";

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

const baseResumeSchema = z.object({
	name: z.string().min(1, "Resume name is required").max(100),
	role_type: z.string().min(1, "Role type is required").max(255),
	summary: z.string().min(1, "Summary is required").max(5000),
});

type BaseResumeFormData = z.infer<typeof baseResumeSchema>;

const DEFAULT_VALUES: BaseResumeFormData = {
	name: "",
	role_type: "",
	summary: "",
};

/** REQ-012 §6.5: Welcome message shown in chat after onboarding completion. */
const WELCOME_MESSAGE =
	"You're all set! I'm scanning for jobs now — I'll let you know what I find.";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Toggle an item in a Set state setter. */
function toggleSetItem(
	setter: React.Dispatch<React.SetStateAction<Set<string>>>,
	id: string,
	checked: boolean,
) {
	setter((prev) => {
		const updated = new Set(prev);
		if (checked) {
			updated.add(id);
		} else {
			updated.delete(id);
		}
		return updated;
	});
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Wraps a checkbox section with a heading and empty-state fallback. */
function CheckboxSection({
	title,
	emptyText,
	hasItems,
	children,
}: {
	title: string;
	emptyText: string;
	hasItems: boolean;
	children: ReactNode;
}) {
	return (
		<div className="space-y-2">
			<h3 className="text-sm font-semibold">{title}</h3>
			{hasItems ? (
				children
			) : (
				<p className="text-muted-foreground text-sm">{emptyText}</p>
			)}
		</div>
	);
}

/** Work history entries with nested bullet checkboxes. */
function WorkHistorySection({
	workHistories,
	selectedJobs,
	selectedBullets,
	onToggleJob,
	onToggleBullet,
}: {
	workHistories: WorkHistory[];
	selectedJobs: Set<string>;
	selectedBullets: Set<string>;
	onToggleJob: (id: string, checked: boolean) => void;
	onToggleBullet: (id: string, checked: boolean) => void;
}) {
	return (
		<CheckboxSection
			title="Work History"
			emptyText="No work history entries"
			hasItems={workHistories.length > 0}
		>
			<div className="space-y-3">
				{workHistories.map((wh) => (
					<div key={wh.id} className="rounded-lg border p-3">
						<div className="flex items-center gap-2">
							<Checkbox
								checked={selectedJobs.has(wh.id)}
								onCheckedChange={(checked) =>
									onToggleJob(wh.id, checked === true)
								}
								data-testid={`job-checkbox-${wh.id}`}
							/>
							<span className="text-sm font-medium">
								{wh.job_title} at {wh.company_name}
							</span>
						</div>
						{wh.bullets.length > 0 && (
							<div className="mt-2 ml-6 space-y-1">
								{wh.bullets.map((bullet) => (
									<div key={bullet.id} className="flex items-start gap-2">
										<Checkbox
											checked={selectedBullets.has(bullet.id)}
											onCheckedChange={(checked) =>
												onToggleBullet(bullet.id, checked === true)
											}
											className="mt-0.5"
											data-testid={`bullet-checkbox-${bullet.id}`}
										/>
										<span className="text-muted-foreground text-sm">
											{bullet.text}
										</span>
									</div>
								))}
							</div>
						)}
					</div>
				))}
			</div>
		</CheckboxSection>
	);
}

/** Education entries with checkboxes. */
function EducationSection({
	educations,
	selectedEducation,
	onToggle,
}: {
	educations: Education[];
	selectedEducation: Set<string>;
	onToggle: (id: string, checked: boolean) => void;
}) {
	return (
		<CheckboxSection
			title="Education"
			emptyText="No education entries"
			hasItems={educations.length > 0}
		>
			<div className="space-y-2">
				{educations.map((edu) => (
					<div key={edu.id} className="flex items-center gap-2">
						<Checkbox
							checked={selectedEducation.has(edu.id)}
							onCheckedChange={(checked) => onToggle(edu.id, checked === true)}
							data-testid={`education-checkbox-${edu.id}`}
						/>
						<span className="text-sm">
							{edu.degree} {edu.field_of_study} &mdash; {edu.institution}
						</span>
					</div>
				))}
			</div>
		</CheckboxSection>
	);
}

/** Certification entries with checkboxes. */
function CertificationsSection({
	certifications,
	selectedCertifications,
	onToggle,
}: {
	certifications: Certification[];
	selectedCertifications: Set<string>;
	onToggle: (id: string, checked: boolean) => void;
}) {
	return (
		<CheckboxSection
			title="Certifications"
			emptyText="No certifications"
			hasItems={certifications.length > 0}
		>
			<div className="space-y-2">
				{certifications.map((cert) => (
					<div key={cert.id} className="flex items-center gap-2">
						<Checkbox
							checked={selectedCertifications.has(cert.id)}
							onCheckedChange={(checked) => onToggle(cert.id, checked === true)}
							data-testid={`certification-checkbox-${cert.id}`}
						/>
						<span className="text-sm">{cert.certification_name}</span>
					</div>
				))}
			</div>
		</CheckboxSection>
	);
}

/** Skill entries with checkboxes. */
function SkillsSection({
	skills,
	selectedSkills,
	onToggle,
}: {
	skills: Skill[];
	selectedSkills: Set<string>;
	onToggle: (id: string, checked: boolean) => void;
}) {
	return (
		<CheckboxSection
			title="Skills"
			emptyText="No skills"
			hasItems={skills.length > 0}
		>
			<div className="flex flex-wrap gap-2">
				{skills.map((skill) => (
					<div
						key={skill.id}
						className="flex items-center gap-2 rounded-md border px-2 py-1"
					>
						<Checkbox
							checked={selectedSkills.has(skill.id)}
							onCheckedChange={(checked) =>
								onToggle(skill.id, checked === true)
							}
							data-testid={`skill-checkbox-${skill.id}`}
						/>
						<span className="text-sm">{skill.skill_name}</span>
					</div>
				))}
			</div>
		</CheckboxSection>
	);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 12: Base Resume Setup.
 *
 * Fetches persona data (work histories, education, certifications, skills)
 * and shows a form with checkbox selections for each category. User fills
 * in resume name, role type, summary, then selects items to include.
 * POST creates the base resume and advances to completion.
 */
export function BaseResumeSetupStep() {
	const { personaId, completeOnboarding, back } = useOnboarding();
	const { addSystemMessage } = useChat();
	const router = useRouter();

	const [isLoading, setIsLoading] = useState(!!personaId);
	const [workHistories, setWorkHistories] = useState<WorkHistory[]>([]);
	const [educations, setEducations] = useState<Education[]>([]);
	const [certifications, setCertifications] = useState<Certification[]>([]);
	const [skills, setSkills] = useState<Skill[]>([]);

	// Checkbox selection state
	const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set());
	const [selectedBullets, setSelectedBullets] = useState<Set<string>>(
		new Set(),
	);
	const [selectedEducation, setSelectedEducation] = useState<Set<string>>(
		new Set(),
	);
	const [selectedCertifications, setSelectedCertifications] = useState<
		Set<string>
	>(new Set());
	const [selectedSkills, setSelectedSkills] = useState<Set<string>>(new Set());

	const [submitError, setSubmitError] = useState<string | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);

	const form = useForm<BaseResumeFormData>({
		resolver: zodResolver(baseResumeSchema),
		defaultValues: DEFAULT_VALUES,
		mode: "onTouched",
	});

	// -----------------------------------------------------------------------
	// Fetch persona data on mount
	// -----------------------------------------------------------------------

	useEffect(() => {
		if (!personaId) return;

		let cancelled = false;

		Promise.all([
			apiGet<ApiListResponse<WorkHistory>>(
				`/personas/${personaId}/work-history`,
			),
			apiGet<ApiListResponse<Education>>(`/personas/${personaId}/education`),
			apiGet<ApiListResponse<Certification>>(
				`/personas/${personaId}/certifications`,
			),
			apiGet<ApiListResponse<Skill>>(`/personas/${personaId}/skills`),
		])
			.then(([whRes, eduRes, certRes, skillRes]) => {
				if (cancelled) return;
				setWorkHistories(whRes.data);
				setEducations(eduRes.data);
				setCertifications(certRes.data);
				setSkills(skillRes.data);

				// Default all items to checked
				setSelectedJobs(new Set(whRes.data.map((wh) => wh.id)));
				setSelectedBullets(
					new Set(whRes.data.flatMap((wh) => wh.bullets.map((b) => b.id))),
				);
				setSelectedEducation(new Set(eduRes.data.map((e) => e.id)));
				setSelectedCertifications(new Set(certRes.data.map((c) => c.id)));
				setSelectedSkills(new Set(skillRes.data.map((s) => s.id)));
			})
			.catch(() => {
				// Fetch failed — show form with empty data
			})
			.finally(() => {
				if (!cancelled) setIsLoading(false);
			});

		return () => {
			cancelled = true;
		};
	}, [personaId]);

	// -----------------------------------------------------------------------
	// Checkbox handlers
	// -----------------------------------------------------------------------

	const toggleJob = useCallback(
		(jobId: string, checked: boolean) => {
			toggleSetItem(setSelectedJobs, jobId, checked);

			// When unchecking a job, also uncheck all its bullets
			if (!checked) {
				const job = workHistories.find((wh) => wh.id === jobId);
				if (job) {
					setSelectedBullets((prev) => {
						const updated = new Set(prev);
						for (const b of job.bullets) {
							updated.delete(b.id);
						}
						return updated;
					});
				}
			}
		},
		[workHistories],
	);

	const toggleBullet = useCallback((bulletId: string, checked: boolean) => {
		toggleSetItem(setSelectedBullets, bulletId, checked);
	}, []);

	// -----------------------------------------------------------------------
	// Submit handler
	// -----------------------------------------------------------------------

	const onSubmit = useCallback(
		async (data: BaseResumeFormData) => {
			if (!personaId) return;

			setSubmitError(null);
			setIsSubmitting(true);

			// Build job_bullet_selections: only include bullets for selected jobs
			const jobBulletSelections: Record<string, string[]> = {};
			for (const jobId of selectedJobs) {
				const job = workHistories.find((wh) => wh.id === jobId);
				if (job) {
					const selectedJobBullets = job.bullets
						.filter((b) => selectedBullets.has(b.id))
						.map((b) => b.id);
					jobBulletSelections[jobId] = selectedJobBullets;
				}
			}

			try {
				await apiPost("/base-resumes", {
					persona_id: personaId,
					name: data.name,
					role_type: data.role_type,
					summary: data.summary,
					included_jobs: Array.from(selectedJobs),
					included_education: Array.from(selectedEducation),
					included_certifications: Array.from(selectedCertifications),
					skills_emphasis: Array.from(selectedSkills),
					job_bullet_selections: jobBulletSelections,
					job_bullet_order: jobBulletSelections,
					is_primary: true,
				});
				await completeOnboarding();
				addSystemMessage(WELCOME_MESSAGE);
				router.replace("/");
			} catch (err) {
				setIsSubmitting(false);
				setSubmitError(toFriendlyError(err));
			}
		},
		[
			personaId,
			completeOnboarding,
			addSystemMessage,
			router,
			selectedJobs,
			selectedBullets,
			selectedEducation,
			selectedCertifications,
			selectedSkills,
			workHistories,
		],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-base-resume-setup"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">
					Loading your persona data...
				</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div className="text-center">
				<h2 className="text-lg font-semibold">Base Resume Setup</h2>
				<p className="text-muted-foreground mt-1">
					Create your first base resume. Select which items to include.
				</p>
			</div>

			<Form {...form}>
				<form
					id="base-resume-form"
					onSubmit={form.handleSubmit(onSubmit)}
					className="space-y-6"
					data-testid="base-resume-form"
					noValidate
				>
					<FormInputField
						control={form.control}
						name="name"
						label="Resume Name"
						placeholder='e.g., "Scrum Master Resume"'
					/>

					<FormInputField
						control={form.control}
						name="role_type"
						label="Role Type"
						placeholder='e.g., "Scrum Master"'
					/>

					<FormField
						control={form.control}
						name="summary"
						render={({ field }) => (
							<FormItem>
								<FormLabel>Summary</FormLabel>
								<FormControl>
									<Textarea
										placeholder="Brief professional summary for this resume..."
										className="min-h-[80px] resize-y"
										{...field}
									/>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>

					<WorkHistorySection
						workHistories={workHistories}
						selectedJobs={selectedJobs}
						selectedBullets={selectedBullets}
						onToggleJob={toggleJob}
						onToggleBullet={toggleBullet}
					/>

					<EducationSection
						educations={educations}
						selectedEducation={selectedEducation}
						onToggle={(id, checked) =>
							toggleSetItem(setSelectedEducation, id, checked)
						}
					/>

					<CertificationsSection
						certifications={certifications}
						selectedCertifications={selectedCertifications}
						onToggle={(id, checked) =>
							toggleSetItem(setSelectedCertifications, id, checked)
						}
					/>

					<SkillsSection
						skills={skills}
						selectedSkills={selectedSkills}
						onToggle={(id, checked) =>
							toggleSetItem(setSelectedSkills, id, checked)
						}
					/>

					<FormErrorSummary className="mt-2" />

					{submitError && (
						<div
							role="alert"
							className="text-destructive text-sm font-medium"
							data-testid="submit-error"
						>
							{submitError}
						</div>
					)}
				</form>
			</Form>

			{/* Navigation */}
			<div className="flex items-center justify-between pt-4">
				<Button
					type="button"
					variant="ghost"
					onClick={back}
					data-testid="back-button"
				>
					<ArrowLeft className="mr-2 h-4 w-4" />
					Back
				</Button>
				<Button
					type="submit"
					form="base-resume-form"
					disabled={isSubmitting}
					data-testid="submit-button"
				>
					{isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
					{isSubmitting ? "Creating..." : "Create Resume"}
				</Button>
			</div>
		</div>
	);
}
