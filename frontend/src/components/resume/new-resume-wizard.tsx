"use client";

/**
 * @fileoverview New resume creation wizard with persona item selection and template picker.
 *
 * Layer: component
 * Feature: resume
 *
 * REQ-012 §9.2, §6.3.12: Form for creating a base resume —
 * name, role type, summary, hierarchical job/bullet checkboxes,
 * education/certification/skill selection, POST to /base-resumes.
 * REQ-025 §6.3: Template selection during resume creation.
 * REQ-026 §3.1–§3.2: Two creation paths — "Generate with AI" vs "Start from Template".
 *
 * Coordinates with:
 * - lib/api-client.ts: apiGet, apiPost for persona data fetching and resume creation
 * - lib/form-errors.ts: toFriendlyError for error display
 * - lib/query-keys.ts: queryKeys for work history, education, certifications, skills, base resumes
 * - lib/toast.ts: showToast for success/error feedback
 * - hooks/use-resume-content-selection.ts: useResumeContentSelection for checkbox state management
 * - components/resume/creation-method-buttons.tsx: AI vs template creation path buttons
 * - components/resume/resume-content-checkboxes.tsx: hierarchical job/education/skill checkboxes
 * - components/editor/template-picker.tsx: template selection grid
 * - components/ui/error-states.tsx: FailedState error display
 * - types/api.ts: ApiListResponse, ApiResponse envelopes
 * - types/persona.ts: WorkHistory, Education, Certification, Skill types
 * - types/resume.ts: BaseResume type
 *
 * Called by / Used by:
 * - app/(main)/resumes/new/page.tsx: new resume creation page
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
import { useResumeContentSelection } from "@/hooks/use-resume-content-selection";
import {
	CreationMethodButtons,
	type CreationMethod,
} from "@/components/resume/creation-method-buttons";
import { ResumeContentCheckboxes } from "@/components/resume/resume-content-checkboxes";
import { TemplatePicker } from "@/components/editor/template-picker";
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
const LABEL_CLASSES = "mb-2 block text-sm font-medium";
const INPUT_CLASSES =
	"border-input bg-background w-full rounded-md border px-3 py-2 text-sm";

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
	const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(
		null,
	);
	const selection = useResumeContentSelection();
	const [isCreating, setIsCreating] = useState(false);
	const [defaultsInitialized, setDefaultsInitialized] = useState(false);

	// Default education and certifications to all selected (§6.3.12)
	useEffect(() => {
		if (!defaultsInitialized && educations.length > 0) {
			selection.setIncludedEducation(educations.map((e) => e.id));
		}
	}, [defaultsInitialized, educations, selection]);

	useEffect(() => {
		if (!defaultsInitialized && certifications.length > 0) {
			selection.setIncludedCertifications(certifications.map((c) => c.id));
		}
	}, [defaultsInitialized, certifications, selection]);

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

	const canSubmit =
		name.trim().length > 0 &&
		roleType.trim().length > 0 &&
		summary.trim().length > 0 &&
		!isCreating;

	const handleCreate = useCallback(
		async (method: CreationMethod) => {
			if (!canSubmit) return;
			setIsCreating(true);
			try {
				const response = await apiPost<ApiResponse<BaseResume>>(
					"/base-resumes",
					{
						persona_id: personaId,
						name: name.trim(),
						role_type: roleType.trim(),
						summary: summary.trim(),
						template_id: selectedTemplateId,
						included_jobs: selection.includedJobs,
						included_education: selection.includedEducation,
						included_certifications: selection.includedCertifications,
						skills_emphasis: selection.skillsEmphasis,
						job_bullet_selections: selection.bulletSelections,
						job_bullet_order: selection.bulletOrder,
					},
				);
				showToast.success("Resume created.");
				await queryClient.invalidateQueries({
					queryKey: queryKeys.baseResumes,
				});
				router.push(`/resumes/${response.data.id}?method=${method}`);
			} catch (err) {
				showToast.error(toFriendlyError(err));
			} finally {
				setIsCreating(false);
			}
		},
		[
			canSubmit,
			personaId,
			name,
			roleType,
			summary,
			selectedTemplateId,
			selection,
			queryClient,
			router,
		],
	);

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
				<label htmlFor="resume-name" className={LABEL_CLASSES}>
					Name
				</label>
				<input
					id="resume-name"
					type="text"
					value={name}
					onChange={(e) => setName(e.target.value)}
					maxLength={MAX_NAME_LENGTH}
					placeholder="e.g. Scrum Master"
					className={INPUT_CLASSES}
				/>
			</div>

			{/* Role Type */}
			<div className="mb-6">
				<label htmlFor="resume-role-type" className={LABEL_CLASSES}>
					Role Type
				</label>
				<input
					id="resume-role-type"
					type="text"
					value={roleType}
					onChange={(e) => setRoleType(e.target.value)}
					maxLength={MAX_ROLE_TYPE_LENGTH}
					placeholder="e.g. Scrum Master roles"
					className={INPUT_CLASSES}
				/>
			</div>

			{/* Summary */}
			<div className="mb-8">
				<label htmlFor="resume-summary" className={LABEL_CLASSES}>
					Summary
				</label>
				<textarea
					id="resume-summary"
					value={summary}
					onChange={(e) => setSummary(e.target.value)}
					rows={5}
					maxLength={MAX_SUMMARY_LENGTH}
					placeholder="Professional summary for this resume..."
					className={INPUT_CLASSES}
				/>
			</div>

			{/* Template picker */}
			<div className="mb-8">
				<h2 className="mb-3 text-sm font-medium">Template</h2>
				<TemplatePicker
					selectedId={selectedTemplateId}
					onSelect={setSelectedTemplateId}
				/>
			</div>

			{/* Content selection checkboxes */}
			<ResumeContentCheckboxes
				jobs={jobs}
				educations={educations}
				certifications={certifications}
				skills={skills}
				selection={selection}
			/>

			{/* Creation method */}
			<CreationMethodButtons
				isCreating={isCreating}
				canSubmit={canSubmit}
				onCreate={handleCreate}
			/>
		</div>
	);
}
