/**
 * Data fetching, state management, and handlers for the resume detail page.
 *
 * REQ-012 §9.2: Base resume editor with content selection.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { useResumeContentSelection } from "@/hooks/use-resume-content-selection";
import type { UseResumeContentSelectionReturn } from "@/hooks/use-resume-content-selection";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type {
	Bullet,
	Certification,
	Education,
	Skill,
	WorkHistory,
} from "@/types/persona";
import type { BaseResume } from "@/types/resume";
import type {
	GenerateResumeResponse,
	GenerationMethod,
	GenerationOptions,
} from "@/types/resume-generation";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UseResumeDetailOptions {
	resumeId: string;
	personaId: string;
}

interface UseResumeDetailReturn {
	isLoading: boolean;
	resumeError: Error | null;
	refetchResume: () => Promise<unknown>;
	resume: BaseResume | undefined;
	jobs: WorkHistory[];
	educations: Education[];
	certifications: Certification[];
	skills: Skill[];
	summary: string;
	setSummary: React.Dispatch<React.SetStateAction<string>>;
	selection: UseResumeContentSelectionReturn;
	isSaving: boolean;
	isRendering: boolean;
	isGenerating: boolean;
	handleSave: () => Promise<void>;
	handleRenderPdf: () => Promise<void>;
	handleReorderBullets: (jobId: string, reorderedBullets: Bullet[]) => void;
	handleGenerate: (
		method: GenerationMethod,
		options?: GenerationOptions,
	) => Promise<GenerateResumeResponse | null>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useResumeDetail({
	resumeId,
	personaId,
}: UseResumeDetailOptions): UseResumeDetailReturn {
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
	const [isGenerating, setIsGenerating] = useState(false);

	const {
		setIncludedJobs,
		setBulletSelections,
		setBulletOrder,
		setIncludedEducation,
		setIncludedCertifications,
		setSkillsEmphasis,
	} = selection;

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
	}, [
		resume,
		isInitialized,
		educations,
		certifications,
		setIncludedJobs,
		setBulletSelections,
		setBulletOrder,
		setIncludedEducation,
		setIncludedCertifications,
		setSkillsEmphasis,
	]);

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

	const handleGenerate = useCallback(
		async (
			method: GenerationMethod,
			options?: GenerationOptions,
		): Promise<GenerateResumeResponse | null> => {
			setIsGenerating(true);
			try {
				const body: Record<string, unknown> = { method };
				if (options) {
					body.page_limit = options.pageLimit;
					body.emphasis = options.emphasis;
					body.include_sections = options.includeSections;
				}
				const result = await apiPost<ApiResponse<GenerateResumeResponse>>(
					`/base-resumes/${resumeId}/generate`,
					body,
				);
				showToast.success("Resume generated.");
				await queryClient.invalidateQueries({
					queryKey: queryKeys.baseResume(resumeId),
				});
				return result.data;
			} catch (err) {
				// 402 toast is handled by api-client; surface other errors
				if (!(err instanceof ApiError && err.status === 402)) {
					showToast.error("Failed to generate resume.");
				}
				return null;
			} finally {
				setIsGenerating(false);
			}
		},
		[resumeId, queryClient],
	);

	// -----------------------------------------------------------------------
	// Aggregate loading state
	// -----------------------------------------------------------------------

	const isLoading =
		resumeLoading ||
		workHistoryLoading ||
		educationLoading ||
		certificationLoading ||
		skillLoading;

	return {
		isLoading,
		resumeError,
		refetchResume,
		resume,
		jobs,
		educations,
		certifications,
		skills,
		summary,
		setSummary,
		selection,
		isSaving,
		isRendering,
		isGenerating,
		handleSave,
		handleRenderPdf,
		handleReorderBullets,
		handleGenerate,
	};
}
