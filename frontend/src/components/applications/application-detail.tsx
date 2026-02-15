"use client";

/**
 * Application detail page component.
 *
 * REQ-012 §11.2: Header with back link, job title/company, applied date,
 * status badge with interview stage, documents panel (resume, cover letter,
 * job snapshot), and editable notes section.
 */

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Download, ExternalLink, Loader2 } from "lucide-react";

import { ApiError, apiGet, apiPatch, buildUrl } from "@/lib/api-client";
import { formatDateTimeAgo } from "@/lib/job-formatters";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { isSafeUrl } from "@/lib/url-utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FailedState, NotFoundState } from "@/components/ui/error-states";
import { StatusBadge } from "@/components/ui/status-badge";
import { Textarea } from "@/components/ui/textarea";
import { StatusTransitionDropdown } from "./status-transition-dropdown";
import type { ApiResponse } from "@/types/api";
import type { Application } from "@/types/application";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NOTES_MAX_LENGTH = 10_000;
const NOTES_SAVE_ERROR = "Failed to save notes.";
const NOTES_SAVE_SUCCESS = "Notes updated.";
const NOTES_PLACEHOLDER = "No notes yet.";
const DOT_SEPARATOR = " \u00b7 ";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ApplicationDetailProps {
	applicationId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ApplicationDetail({ applicationId }: ApplicationDetailProps) {
	const router = useRouter();
	const queryClient = useQueryClient();

	// -----------------------------------------------------------------------
	// Data fetching
	// -----------------------------------------------------------------------

	const { data, isLoading, error, refetch } = useQuery({
		queryKey: queryKeys.application(applicationId),
		queryFn: () =>
			apiGet<ApiResponse<Application>>(`/applications/${applicationId}`),
	});

	// -----------------------------------------------------------------------
	// Notes state
	// -----------------------------------------------------------------------

	const [editingNotes, setEditingNotes] = useState(false);
	const [notesText, setNotesText] = useState("");
	const [savingNotes, setSavingNotes] = useState(false);

	const handleEditNotes = useCallback(() => {
		setNotesText(data?.data.notes ?? "");
		setEditingNotes(true);
	}, [data]);

	const handleCancelNotes = useCallback(() => {
		setEditingNotes(false);
		setNotesText("");
	}, []);

	const handleSaveNotes = useCallback(async () => {
		setSavingNotes(true);
		try {
			await apiPatch(`/applications/${applicationId}`, {
				notes: notesText,
			});
			await queryClient.invalidateQueries({
				queryKey: queryKeys.application(applicationId),
			});
			showToast.success(NOTES_SAVE_SUCCESS);
			setEditingNotes(false);
		} catch {
			showToast.error(NOTES_SAVE_ERROR);
		} finally {
			setSavingNotes(false);
		}
	}, [applicationId, notesText, queryClient]);

	// -----------------------------------------------------------------------
	// Loading / Error
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div data-testid="loading-spinner" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (error) {
		if (error instanceof ApiError && error.status === 404) {
			return (
				<NotFoundState
					itemType="application"
					onBack={() => router.push("/applications")}
				/>
			);
		}
		return <FailedState onRetry={() => refetch()} />;
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	const app = data!.data;
	const { job_snapshot: snapshot } = app;

	return (
		<div data-testid="application-detail">
			{/* Back link */}
			<Link
				href="/applications"
				data-testid="back-to-applications"
				className="text-muted-foreground hover:text-foreground mb-6 inline-flex items-center gap-1 text-sm"
			>
				<ArrowLeft className="h-4 w-4" />
				Back to Applications
			</Link>

			{/* Header */}
			<div data-testid="application-header" className="mt-4 space-y-2">
				<h1 className="text-2xl font-bold">{snapshot.title}</h1>
				<p className="text-muted-foreground text-lg">{snapshot.company_name}</p>
				<div className="flex items-center gap-2 text-sm">
					<span className="text-muted-foreground">
						Applied {formatDateTimeAgo(app.applied_at)}
					</span>
					<span className="text-muted-foreground">{DOT_SEPARATOR}</span>
					<StatusBadge status={app.status} />
					{app.current_interview_stage && (
						<span className="bg-warning/20 text-warning-foreground inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium">
							{app.current_interview_stage}
						</span>
					)}
					<StatusTransitionDropdown
						applicationId={applicationId}
						currentStatus={app.status}
					/>
				</div>
			</div>

			{/* Two-column layout: Documents + placeholder for Timeline */}
			<div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
				{/* Documents Panel */}
				<div data-testid="documents-panel" className="space-y-4">
					<h2 className="text-lg font-semibold">Documents</h2>

					{/* Resume */}
					<Card>
						<CardHeader>
							<CardTitle className="text-sm">Resume</CardTitle>
						</CardHeader>
						<CardContent>
							{app.submitted_resume_pdf_id ? (
								<div className="flex items-center gap-2">
									<Button
										variant="outline"
										size="sm"
										asChild
										data-testid="resume-download"
									>
										<a
											href={buildUrl(
												`/submitted-resume-pdfs/${app.submitted_resume_pdf_id}/download`,
											)}
											target="_blank"
											rel="noopener noreferrer"
										>
											<Download className="mr-1 h-4 w-4" />
											Download
										</a>
									</Button>
								</div>
							) : (
								<p className="text-muted-foreground text-sm">
									No PDF submitted yet.
								</p>
							)}
						</CardContent>
					</Card>

					{/* Cover Letter */}
					{app.cover_letter_id && (
						<Card data-testid="cover-letter-section">
							<CardHeader>
								<CardTitle className="text-sm">Cover Letter</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="flex items-center gap-2">
									{app.submitted_cover_letter_pdf_id && (
										<Button
											variant="outline"
											size="sm"
											asChild
											data-testid="cover-letter-download"
										>
											<a
												href={buildUrl(
													`/submitted-cover-letter-pdfs/${app.submitted_cover_letter_pdf_id}/download`,
												)}
												target="_blank"
												rel="noopener noreferrer"
											>
												<Download className="mr-1 h-4 w-4" />
												Download
											</a>
										</Button>
									)}
								</div>
							</CardContent>
						</Card>
					)}

					{/* Job Snapshot */}
					<Card data-testid="job-snapshot-section">
						<CardHeader>
							<CardTitle className="text-sm">Job Snapshot</CardTitle>
						</CardHeader>
						<CardContent>
							<p className="text-muted-foreground mb-2 text-sm">
								Captured {formatDateTimeAgo(snapshot.captured_at)}
							</p>
							<div className="flex items-center gap-2">
								{snapshot.source_url && isSafeUrl(snapshot.source_url) && (
									<Button
										variant="outline"
										size="sm"
										asChild
										data-testid="view-live-posting"
									>
										<a
											href={snapshot.source_url}
											target="_blank"
											rel="noopener noreferrer"
										>
											<ExternalLink className="mr-1 h-4 w-4" />
											View live posting
										</a>
									</Button>
								)}
							</div>
						</CardContent>
					</Card>
				</div>
			</div>

			{/* Notes Section */}
			<div data-testid="notes-section" className="mt-6">
				<div className="flex items-center justify-between">
					<h2 className="text-lg font-semibold">Notes</h2>
					{!editingNotes && (
						<Button
							variant="outline"
							size="sm"
							data-testid="notes-edit-button"
							onClick={handleEditNotes}
						>
							Edit
						</Button>
					)}
				</div>
				{editingNotes ? (
					<div className="mt-2 space-y-2">
						<Textarea
							data-testid="notes-textarea"
							value={notesText}
							onChange={(e) => setNotesText(e.target.value)}
							maxLength={NOTES_MAX_LENGTH}
							rows={6}
							placeholder="Add notes about this application..."
						/>
						<div className="flex items-center justify-between">
							<span
								data-testid="notes-char-count"
								className="text-muted-foreground text-xs"
							>
								{notesText.length}/{NOTES_MAX_LENGTH}
							</span>
							<div className="flex gap-2">
								<Button
									variant="ghost"
									size="sm"
									data-testid="notes-cancel-button"
									onClick={handleCancelNotes}
									disabled={savingNotes}
								>
									Cancel
								</Button>
								<Button
									size="sm"
									data-testid="notes-save-button"
									onClick={handleSaveNotes}
									disabled={savingNotes}
									className="gap-2"
								>
									{savingNotes && <Loader2 className="h-4 w-4 animate-spin" />}
									Save
								</Button>
							</div>
						</div>
					</div>
				) : (
					<p className="text-muted-foreground mt-2 text-sm whitespace-pre-wrap">
						{app.notes ?? NOTES_PLACEHOLDER}
					</p>
				)}
			</div>
		</div>
	);
}
