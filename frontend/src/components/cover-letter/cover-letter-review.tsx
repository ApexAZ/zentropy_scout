"use client";

/**
 * Cover letter review with agent reasoning, stories used,
 * editable textarea, word count indicator, validation display,
 * and voice check badge.
 *
 * REQ-012 §10.2: Cover letter review component.
 * REQ-012 §10.3: Validation display with error/warning banners.
 */

import { Fragment, useCallback, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Download, Loader2, X } from "lucide-react";

import { apiGet, apiPatch, buildUrl } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { AgentReasoning } from "@/components/ui/agent-reasoning";
import { Button } from "@/components/ui/button";
import { FailedState } from "@/components/ui/error-states";
import { StatusBadge } from "@/components/ui/status-badge";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { CoverLetter, ValidationIssue } from "@/types/application";
import type { PersonaJobResponse } from "@/types/job";
import type { AchievementStory, Skill, VoiceProfile } from "@/types/persona";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_DRAFT_LENGTH = 10000;
const WORD_COUNT_MIN = 250;
const WORD_COUNT_MAX = 350;

const LOADING_SPINNER = (
	<div data-testid="loading-spinner" className="flex justify-center py-8">
		<Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
	</div>
);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CoverLetterReviewProps {
	coverLetterId: string;
	hideActions?: boolean;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StoriesUsed({
	stories,
	skillMap,
}: Readonly<{
	stories: AchievementStory[];
	skillMap: Map<string, string>;
}>) {
	return (
		<div data-testid="stories-used" className="mt-4">
			<h2 className="mb-2 text-sm font-semibold">Stories Used</h2>
			<ul className="space-y-1 pl-5">
				{stories.map((story) => {
					const skillNames = story.skills_demonstrated
						.map((id) => skillMap.get(id))
						.filter(Boolean);

					return (
						<li key={story.id} className="text-sm">
							<span className="font-medium">{story.title}</span>
							{skillNames.length > 0 && (
								<span className="text-muted-foreground ml-1">
									(
									{skillNames.map((name, idx) => (
										<Fragment key={name}>
											{idx > 0 && ", "}
											<span>{name}</span>
										</Fragment>
									))}
									)
								</span>
							)}
						</li>
					);
				})}
			</ul>
		</div>
	);
}

function WordCount({ text }: Readonly<{ text: string }>) {
	const wordCount = text.split(/\s+/).filter(Boolean).length;
	const inRange = wordCount >= WORD_COUNT_MIN && wordCount <= WORD_COUNT_MAX;

	return (
		<div
			data-testid="word-count"
			data-in-range={inRange ? "true" : "false"}
			className={`mt-2 text-sm ${inRange ? "text-green-600 dark:text-green-400" : "text-amber-600 dark:text-amber-400"}`}
		>
			Word count: {wordCount} / {WORD_COUNT_MIN}–{WORD_COUNT_MAX} target{" "}
			{inRange ? "✓" : ""}
		</div>
	);
}

function ValidationErrors({ issues }: Readonly<{ issues: ValidationIssue[] }>) {
	return (
		<div
			data-testid="validation-errors"
			role="alert"
			className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950"
		>
			<div className="mb-2 flex items-center gap-2">
				<X className="h-4 w-4 text-red-600 dark:text-red-400" />
				<span className="text-sm font-semibold text-red-800 dark:text-red-200">
					Validation Error
				</span>
			</div>
			<ul className="list-disc space-y-1 pl-5 text-sm text-red-700 dark:text-red-300">
				{issues.map((issue) => (
					<li key={issue.rule}>{issue.message}</li>
				))}
			</ul>
		</div>
	);
}

function ValidationWarnings({
	issues,
}: Readonly<{ issues: ValidationIssue[] }>) {
	return (
		<output
			data-testid="validation-warnings"
			className="mt-4 block rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950"
		>
			<div className="mb-2 flex items-center gap-2">
				<AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
				<span className="text-sm font-semibold text-amber-800 dark:text-amber-200">
					Warning
				</span>
			</div>
			<ul className="list-disc space-y-1 pl-5 text-sm text-amber-700 dark:text-amber-300">
				{issues.map((issue) => (
					<li key={issue.rule}>{issue.message}</li>
				))}
			</ul>
		</output>
	);
}

function VoiceCheckBadge({ tone }: Readonly<{ tone: string }>) {
	return (
		<div
			data-testid="voice-check"
			className="text-muted-foreground mt-1 text-sm"
		>
			Voice: &quot;{tone}&quot; ✓
		</div>
	);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CoverLetterReview({
	coverLetterId,
	hideActions,
}: Readonly<CoverLetterReviewProps>) {
	const queryClient = useQueryClient();

	// -----------------------------------------------------------------------
	// Data fetching
	// -----------------------------------------------------------------------

	const {
		data: coverLetterData,
		isLoading: coverLetterLoading,
		error: coverLetterError,
	} = useQuery({
		queryKey: queryKeys.coverLetter(coverLetterId),
		queryFn: () =>
			apiGet<ApiResponse<CoverLetter>>(`/cover-letters/${coverLetterId}`),
	});

	const coverLetter = coverLetterData?.data;

	const { data: jobPostingData, error: jobPostingError } = useQuery({
		queryKey: queryKeys.job(coverLetter?.job_posting_id ?? ""),
		queryFn: () =>
			apiGet<ApiResponse<PersonaJobResponse>>(
				`/job-postings/${coverLetter?.job_posting_id}`,
			),
		enabled: !!coverLetter?.job_posting_id,
	});

	const { data: storiesData, error: storiesError } = useQuery({
		queryKey: queryKeys.achievementStories(coverLetter?.persona_id ?? ""),
		queryFn: () =>
			apiGet<ApiListResponse<AchievementStory>>(
				`/personas/${coverLetter?.persona_id}/achievement-stories`,
			),
		enabled: !!coverLetter?.persona_id,
	});

	const { data: skillsData, error: skillsError } = useQuery({
		queryKey: queryKeys.skills(coverLetter?.persona_id ?? ""),
		queryFn: () =>
			apiGet<ApiListResponse<Skill>>(
				`/personas/${coverLetter?.persona_id}/skills`,
			),
		enabled: !!coverLetter?.persona_id,
	});

	const { data: voiceProfileData } = useQuery({
		queryKey: queryKeys.voiceProfile(coverLetter?.persona_id ?? ""),
		queryFn: () =>
			apiGet<ApiResponse<VoiceProfile>>(
				`/personas/${coverLetter?.persona_id}/voice-profile`,
			),
		enabled: !!coverLetter?.persona_id,
	});

	// -----------------------------------------------------------------------
	// Derived state
	// -----------------------------------------------------------------------

	const jobPosting = jobPostingData?.data?.job;
	const allStories = useMemo(
		() => storiesData?.data ?? [],
		[storiesData?.data],
	);
	const allSkills = useMemo(() => skillsData?.data ?? [], [skillsData?.data]);

	const skillMap = useMemo(() => {
		const map = new Map<string, string>();
		for (const skill of allSkills) {
			map.set(skill.id, skill.skill_name);
		}
		return map;
	}, [allSkills]);

	const usedStories = useMemo(() => {
		if (!coverLetter) return [];
		const usedIds = new Set(coverLetter.achievement_stories_used);
		return allStories.filter((s) => usedIds.has(s.id));
	}, [coverLetter, allStories]);

	const voiceProfile = voiceProfileData?.data ?? null;

	const validationErrors = useMemo(
		() =>
			coverLetter?.validation_result?.issues.filter(
				(i) => i.severity === "error",
			) ?? [],
		[coverLetter?.validation_result],
	);

	const validationWarnings = useMemo(
		() =>
			coverLetter?.validation_result?.issues.filter(
				(i) => i.severity === "warning",
			) ?? [],
		[coverLetter?.validation_result],
	);

	// -----------------------------------------------------------------------
	// Form state
	// -----------------------------------------------------------------------

	const [draftText, setDraftText] = useState<string | null>(null);
	const [isApproving, setIsApproving] = useState(false);
	const isReadOnly = coverLetter?.status !== "Draft";
	const displayText = isReadOnly
		? (coverLetter?.final_text ?? coverLetter?.draft_text ?? "")
		: (draftText ?? coverLetter?.draft_text ?? "");

	const handleTextChange = useCallback(
		(e: React.ChangeEvent<HTMLTextAreaElement>) => {
			setDraftText(e.target.value);
		},
		[],
	);

	const handleApprove = useCallback(async () => {
		setIsApproving(true);
		try {
			await apiPatch(`/cover-letters/${coverLetterId}`, {
				status: "Approved",
			});
			await queryClient.invalidateQueries({
				queryKey: queryKeys.coverLetter(coverLetterId),
			});
			showToast.success("Cover letter approved.");
		} catch (err) {
			setIsApproving(false);
			showToast.error(toFriendlyError(err));
		}
	}, [coverLetterId, queryClient]);

	// -----------------------------------------------------------------------
	// Loading / Error — staged checks for dependent queries
	// -----------------------------------------------------------------------

	// Stage 1: primary query
	if (coverLetterLoading) {
		return LOADING_SPINNER;
	}

	if (coverLetterError || !coverLetter) {
		return <FailedState />;
	}

	// Stage 2: dependent queries (may not have started yet when enabled flips)
	const dependentError = jobPostingError ?? storiesError ?? skillsError;

	if (dependentError) {
		return <FailedState />;
	}

	if (!jobPostingData || !storiesData || !skillsData) {
		return LOADING_SPINNER;
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	const headerTitle = jobPosting
		? `Cover Letter for: ${jobPosting.job_title} at ${jobPosting.company_name}`
		: "Cover Letter Review";

	return (
		<div data-testid="cover-letter-review">
			{/* Header (hidden when embedded in unified review) */}
			{!hideActions && (
				<div className="mb-6 flex items-center gap-3">
					<h1 className="text-xl font-semibold">{headerTitle}</h1>
					<StatusBadge status={coverLetter.status} />
				</div>
			)}

			{/* Agent Reasoning */}
			{coverLetter.agent_reasoning && (
				<AgentReasoning reasoning={coverLetter.agent_reasoning} />
			)}

			{/* Stories Used */}
			{usedStories.length > 0 && (
				<StoriesUsed stories={usedStories} skillMap={skillMap} />
			)}

			{/* Editable Letter Body */}
			<div className="mt-6">
				<label
					htmlFor="cover-letter-body"
					className="mb-2 block text-sm font-semibold"
				>
					Cover Letter
				</label>
				<textarea
					id="cover-letter-body"
					value={displayText}
					onChange={handleTextChange}
					readOnly={isReadOnly}
					rows={12}
					maxLength={MAX_DRAFT_LENGTH}
					className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm"
				/>

				{/* Word Count */}
				<WordCount text={displayText} />

				{/* Voice Check Badge */}
				{voiceProfile && <VoiceCheckBadge tone={voiceProfile.tone} />}
			</div>

			{/* Validation Display (§10.3) */}
			{validationErrors.length > 0 && (
				<ValidationErrors issues={validationErrors} />
			)}
			{validationWarnings.length > 0 && (
				<ValidationWarnings issues={validationWarnings} />
			)}

			{/* Approval Flow (§10.6) — hidden when embedded in unified review */}
			{!hideActions && coverLetter.status === "Draft" && (
				<div className="mt-6">
					<Button
						type="button"
						disabled={isApproving}
						onClick={handleApprove}
						className="gap-2"
					>
						{isApproving && (
							<Loader2
								data-testid="approve-spinner"
								className="h-4 w-4 animate-spin"
								aria-hidden="true"
							/>
						)}
						{isApproving ? "Approving..." : "Approve"}
					</Button>
				</div>
			)}

			{/* PDF Download (§10.6) — hidden when embedded in unified review */}
			{!hideActions && coverLetter.status === "Approved" && (
				<div className="mt-6">
					<Button variant="outline" asChild>
						<a
							data-testid="download-pdf"
							href={buildUrl(
								`/submitted-cover-letter-pdfs/${coverLetterId}/download`,
							)}
							aria-label="Download PDF"
							target="_blank"
							rel="noopener noreferrer"
						>
							<Download className="h-4 w-4" />
							Download PDF
						</a>
					</Button>
				</div>
			)}
		</div>
	);
}
