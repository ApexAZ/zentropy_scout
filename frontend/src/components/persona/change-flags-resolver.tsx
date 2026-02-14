"use client";

/**
 * PersonaChangeFlags resolution UI (§6.13).
 *
 * REQ-012 §7.6: Review each pending change flag and choose
 * "Add to all resumes", "Add to some" (expands base resume
 * checklist), or "Skip". Each flag resolves independently via
 * PATCH /persona-change-flags/:id.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState, FailedState } from "@/components/ui/error-states";
import { apiGet, apiPatch } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import type { ApiListResponse } from "@/types/api";
import type {
	ChangeType,
	ChangeFlagResolution,
	PersonaChangeFlag,
} from "@/types/persona";
import type { BaseResume } from "@/types/resume";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CHANGE_TYPE_LABELS: Record<ChangeType, string> = {
	job_added: "New job",
	bullet_added: "New bullet",
	skill_added: "Added skill",
	education_added: "New education",
	certification_added: "New certification",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ChangeFlagsResolver() {
	const queryClient = useQueryClient();

	const {
		data: flagsResponse,
		isLoading,
		isError,
		refetch,
	} = useQuery({
		queryKey: queryKeys.changeFlags,
		queryFn: () =>
			apiGet<ApiListResponse<PersonaChangeFlag>>("/persona-change-flags", {
				status: "Pending",
			}),
	});

	const [expandedFlagId, setExpandedFlagId] = useState<string | null>(null);

	const { data: resumesResponse } = useQuery({
		queryKey: queryKeys.baseResumes,
		queryFn: () => apiGet<ApiListResponse<BaseResume>>("/base-resumes"),
		enabled: expandedFlagId !== null,
	});

	const [resolvingFlagId, setResolvingFlagId] = useState<string | null>(null);
	const [selectedResumeIds, setSelectedResumeIds] = useState<Set<string>>(
		new Set(),
	);
	const [flagErrors, setFlagErrors] = useState<Record<string, string>>({});

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	async function handleResolve(
		flagId: string,
		resolution: ChangeFlagResolution,
	) {
		setResolvingFlagId(flagId);
		setFlagErrors((prev) => {
			const next = { ...prev };
			delete next[flagId];
			return next;
		});

		try {
			await apiPatch(`/persona-change-flags/${flagId}`, {
				status: "Resolved",
				resolution,
			});
			showToast.success("Change resolved.");
			await queryClient.invalidateQueries({ queryKey: queryKeys.changeFlags });
			if (expandedFlagId === flagId) {
				setExpandedFlagId(null);
				setSelectedResumeIds(new Set());
			}
		} catch (err) {
			setFlagErrors((prev) => ({ ...prev, [flagId]: toFriendlyError(err) }));
		} finally {
			setResolvingFlagId(null);
		}
	}

	function handleExpandAddSome(flagId: string) {
		setExpandedFlagId(flagId);
		setSelectedResumeIds(new Set());
	}

	function handleCancelAddSome() {
		setExpandedFlagId(null);
		setSelectedResumeIds(new Set());
	}

	function handleToggleResume(resumeId: string) {
		setSelectedResumeIds((prev) => {
			const next = new Set(prev);
			if (next.has(resumeId)) {
				next.delete(resumeId);
			} else {
				next.add(resumeId);
			}
			return next;
		});
	}

	// -----------------------------------------------------------------------
	// States
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Loader2
					className="text-muted-foreground size-8 animate-spin"
					data-testid="loading-spinner"
				/>
			</div>
		);
	}

	if (isError) {
		return (
			<FailedState
				message="Failed to load change flags."
				onRetry={() => refetch()}
			/>
		);
	}

	const flags = flagsResponse?.data ?? [];

	if (flags.length === 0) {
		return (
			<div>
				<EmptyState
					title="All changes resolved"
					description="No pending changes to review."
				/>
				<div className="mt-4 text-center">
					<Link
						href="/persona"
						className="text-primary text-sm font-medium hover:underline"
					>
						&larr; Back to Profile
					</Link>
				</div>
			</div>
		);
	}

	const heading =
		flags.length === 1
			? "1 change needs review"
			: `${flags.length} changes need review`;

	const activeResumes =
		resumesResponse?.data.filter((r) => r.status === "Active") ?? [];

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="change-flags-resolver" className="space-y-6">
			<div>
				<h2 className="text-lg font-semibold">{heading}</h2>
				<p className="text-muted-foreground text-sm">
					Review and resolve each change below.
				</p>
			</div>

			<div className="space-y-4">
				{flags.map((flag) => {
					const isResolving = resolvingFlagId === flag.id;
					const isAnyResolving = resolvingFlagId !== null;
					const error = flagErrors[flag.id];

					return (
						<div
							key={flag.id}
							data-testid={`flag-${flag.id}`}
							className="space-y-3 rounded-lg border p-4"
						>
							<div className="flex items-start justify-between gap-4">
								<span className="text-sm">
									<span className="font-medium">
										{CHANGE_TYPE_LABELS[flag.change_type]}:
									</span>{" "}
									{flag.item_description}
								</span>
							</div>

							<div className="flex flex-wrap gap-2">
								<Button
									size="sm"
									data-testid={`add-all-${flag.id}`}
									disabled={isAnyResolving}
									onClick={() => handleResolve(flag.id, "added_to_all")}
								>
									{isResolving ? "Resolving…" : "Add to all resumes"}
								</Button>
								<Button
									size="sm"
									variant="outline"
									data-testid={`add-some-${flag.id}`}
									disabled={isAnyResolving}
									onClick={() => handleExpandAddSome(flag.id)}
								>
									Add to some
								</Button>
								<Button
									size="sm"
									variant="ghost"
									data-testid={`skip-${flag.id}`}
									disabled={isAnyResolving}
									onClick={() => handleResolve(flag.id, "skipped")}
								>
									Skip
								</Button>
							</div>

							{expandedFlagId === flag.id && (
								<div
									data-testid={`resume-checklist-${flag.id}`}
									className="space-y-2 rounded-md border p-3"
								>
									{activeResumes.map((resume) => (
										<label
											key={resume.id}
											className="flex cursor-pointer items-center gap-2 text-sm"
										>
											<Checkbox
												checked={selectedResumeIds.has(resume.id)}
												onCheckedChange={() => handleToggleResume(resume.id)}
											/>
											{resume.name}
										</label>
									))}
									<div className="flex gap-2 pt-2">
										<Button
											size="sm"
											data-testid={`confirm-some-${flag.id}`}
											disabled={selectedResumeIds.size === 0 || isAnyResolving}
											onClick={() => handleResolve(flag.id, "added_to_some")}
										>
											Confirm
										</Button>
										<Button
											size="sm"
											variant="ghost"
											onClick={handleCancelAddSome}
										>
											Cancel
										</Button>
									</div>
								</div>
							)}

							{error && (
								<p
									data-testid={`flag-error-${flag.id}`}
									className="text-destructive text-sm"
								>
									{error}
								</p>
							)}
						</div>
					);
				})}
			</div>

			<Link
				href="/persona"
				className="text-primary text-sm font-medium hover:underline"
			>
				&larr; Back to Profile
			</Link>
		</div>
	);
}
