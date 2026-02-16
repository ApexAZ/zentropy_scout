"use client";

/**
 * Application detail page component.
 *
 * REQ-012 §11.2: Header with back link, job title/company, applied date,
 * status badge with interview stage, documents panel (resume, cover letter,
 * job snapshot), and editable notes section.
 * REQ-012 §11.5: Offer details card with deadline countdown and edit dialog.
 * REQ-012 §11.6: Rejection details card with stage, reason, feedback, and date.
 */

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
	Archive,
	ArchiveRestore,
	ArrowLeft,
	Download,
	Loader2,
	Pin,
} from "lucide-react";

import {
	ApiError,
	apiDelete,
	apiGet,
	apiPatch,
	apiPost,
	buildUrl,
} from "@/lib/api-client";
import { formatDateTimeAgo } from "@/lib/job-formatters";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FailedState, NotFoundState } from "@/components/ui/error-states";
import { StatusBadge } from "@/components/ui/status-badge";
import { Textarea } from "@/components/ui/textarea";
import { OfferDetailsCard } from "./offer-details-card";
import { OfferDetailsDialog } from "./offer-details-dialog";
import { RejectionDetailsCard } from "./rejection-details-card";
import { RejectionDetailsDialog } from "./rejection-details-dialog";
import { AddTimelineEventDialog } from "./add-timeline-event-dialog";
import type { CreateTimelineEventPayload } from "./add-timeline-event-dialog";
import { ApplicationTimeline } from "./application-timeline";
import { JobSnapshotSection } from "./job-snapshot-section";
import { StatusTransitionDropdown } from "./status-transition-dropdown";
import type { ApiResponse } from "@/types/api";
import type {
	Application,
	OfferDetails,
	RejectionDetails,
} from "@/types/application";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NOTES_MAX_LENGTH = 10_000;
const NOTES_SAVE_ERROR = "Failed to save notes.";
const NOTES_SAVE_SUCCESS = "Notes updated.";
const NOTES_PLACEHOLDER = "No notes yet.";
const EVENT_SAVE_ERROR = "Failed to add event.";
const EVENT_SAVE_SUCCESS = "Event added.";
const OFFER_SAVE_ERROR = "Failed to update offer details.";
const OFFER_SAVE_SUCCESS = "Offer details updated.";
const REJECTION_SAVE_ERROR = "Failed to update rejection details.";
const REJECTION_SAVE_SUCCESS = "Rejection details updated.";
const PIN_TOGGLE_ERROR = "Failed to update pin status.";
const PIN_SUCCESS = "Application pinned.";
const UNPIN_SUCCESS = "Application unpinned.";
const ARCHIVE_ERROR = "Failed to archive application.";
const ARCHIVE_SUCCESS = "Application archived.";
const RESTORE_ERROR = "Failed to restore application.";
const RESTORE_SUCCESS = "Application restored.";
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

export function ApplicationDetail({
	applicationId,
}: Readonly<ApplicationDetailProps>) {
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
	// Offer edit state
	// -----------------------------------------------------------------------

	const [showOfferEditDialog, setShowOfferEditDialog] = useState(false);
	const [savingOffer, setSavingOffer] = useState(false);

	const handleEditOffer = useCallback(() => {
		setShowOfferEditDialog(true);
	}, []);

	const handleCancelOfferEdit = useCallback(() => {
		setShowOfferEditDialog(false);
	}, []);

	const handleSaveOffer = useCallback(
		async (details: OfferDetails) => {
			setSavingOffer(true);
			try {
				await apiPatch(`/applications/${applicationId}`, {
					offer_details: details,
				});
				await queryClient.invalidateQueries({
					queryKey: queryKeys.application(applicationId),
				});
				showToast.success(OFFER_SAVE_SUCCESS);
				setShowOfferEditDialog(false);
			} catch {
				showToast.error(OFFER_SAVE_ERROR);
			} finally {
				setSavingOffer(false);
			}
		},
		[applicationId, queryClient],
	);

	// -----------------------------------------------------------------------
	// Rejection edit state
	// -----------------------------------------------------------------------

	const [showRejectionEditDialog, setShowRejectionEditDialog] = useState(false);
	const [savingRejection, setSavingRejection] = useState(false);

	const handleEditRejection = useCallback(() => {
		setShowRejectionEditDialog(true);
	}, []);

	const handleCancelRejectionEdit = useCallback(() => {
		setShowRejectionEditDialog(false);
	}, []);

	const handleSaveRejection = useCallback(
		async (details: RejectionDetails) => {
			setSavingRejection(true);
			try {
				await apiPatch(`/applications/${applicationId}`, {
					rejection_details: details,
				});
				await queryClient.invalidateQueries({
					queryKey: queryKeys.application(applicationId),
				});
				showToast.success(REJECTION_SAVE_SUCCESS);
				setShowRejectionEditDialog(false);
			} catch {
				showToast.error(REJECTION_SAVE_ERROR);
			} finally {
				setSavingRejection(false);
			}
		},
		[applicationId, queryClient],
	);

	// -----------------------------------------------------------------------
	// Add Event state
	// -----------------------------------------------------------------------

	const [showAddEventDialog, setShowAddEventDialog] = useState(false);
	const [savingEvent, setSavingEvent] = useState(false);

	const handleAddEvent = useCallback(() => {
		setShowAddEventDialog(true);
	}, []);

	const handleCancelAddEvent = useCallback(() => {
		setShowAddEventDialog(false);
	}, []);

	const handleSaveEvent = useCallback(
		async (payload: CreateTimelineEventPayload) => {
			setSavingEvent(true);
			try {
				await apiPost(`/applications/${applicationId}/timeline`, payload);
				await queryClient.invalidateQueries({
					queryKey: queryKeys.timelineEvents(applicationId),
				});
				showToast.success(EVENT_SAVE_SUCCESS);
				setShowAddEventDialog(false);
			} catch {
				showToast.error(EVENT_SAVE_ERROR);
			} finally {
				setSavingEvent(false);
			}
		},
		[applicationId, queryClient],
	);

	// -----------------------------------------------------------------------
	// Pin toggle state
	// -----------------------------------------------------------------------

	const [togglingPin, setTogglingPin] = useState(false);

	const handleTogglePin = useCallback(
		async (currentlyPinned: boolean) => {
			setTogglingPin(true);
			try {
				await apiPatch(`/applications/${applicationId}`, {
					is_pinned: !currentlyPinned,
				});
				await queryClient.invalidateQueries({
					queryKey: queryKeys.application(applicationId),
				});
				showToast.success(currentlyPinned ? UNPIN_SUCCESS : PIN_SUCCESS);
			} catch {
				showToast.error(PIN_TOGGLE_ERROR);
			} finally {
				setTogglingPin(false);
			}
		},
		[applicationId, queryClient],
	);

	// -----------------------------------------------------------------------
	// Archive state
	// -----------------------------------------------------------------------

	const [archiving, setArchiving] = useState(false);

	const handleArchive = useCallback(async () => {
		setArchiving(true);
		try {
			await apiDelete(`/applications/${applicationId}`);
			await queryClient.invalidateQueries({
				queryKey: queryKeys.applications,
			});
			showToast.success(ARCHIVE_SUCCESS);
			router.push("/applications");
		} catch {
			showToast.error(ARCHIVE_ERROR);
		} finally {
			setArchiving(false);
		}
	}, [applicationId, queryClient, router]);

	// -----------------------------------------------------------------------
	// Restore state
	// -----------------------------------------------------------------------

	const [restoring, setRestoring] = useState(false);

	const handleRestore = useCallback(async () => {
		setRestoring(true);
		try {
			await apiPost(`/applications/${applicationId}/restore`);
			await queryClient.invalidateQueries({
				queryKey: queryKeys.application(applicationId),
			});
			showToast.success(RESTORE_SUCCESS);
		} catch {
			showToast.error(RESTORE_ERROR);
		} finally {
			setRestoring(false);
		}
	}, [applicationId, queryClient]);

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
	const showOfferCard =
		app.offer_details !== null &&
		(app.status === "Offer" || app.status === "Accepted");
	const showRejectionCard =
		app.rejection_details !== null && app.status === "Rejected";

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
						currentInterviewStage={app.current_interview_stage}
					/>
					<Button
						variant="ghost"
						size="sm"
						data-testid="pin-toggle"
						aria-label={app.is_pinned ? "Unpin application" : "Pin application"}
						onClick={() => handleTogglePin(app.is_pinned)}
						disabled={togglingPin}
					>
						<Pin className={cn("h-4 w-4", app.is_pinned && "fill-current")} />
					</Button>
				</div>
			</div>

			{/* Archive / Restore action bar */}
			<div className="mt-4 flex gap-2">
				{app.archived_at === null ? (
					<Button
						variant="outline"
						size="sm"
						data-testid="archive-button"
						onClick={handleArchive}
						disabled={archiving}
					>
						<Archive className="mr-1 h-4 w-4" />
						Archive
					</Button>
				) : (
					<Button
						variant="outline"
						size="sm"
						data-testid="restore-button"
						onClick={handleRestore}
						disabled={restoring}
					>
						<ArchiveRestore className="mr-1 h-4 w-4" />
						Restore
					</Button>
				)}
			</div>

			{/* Two-column layout: Documents + Timeline */}
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
					<JobSnapshotSection snapshot={snapshot} />
				</div>

				{/* Timeline Panel */}
				<div data-testid="timeline-panel">
					<ApplicationTimeline
						applicationId={applicationId}
						onAddEvent={handleAddEvent}
					/>
					<AddTimelineEventDialog
						open={showAddEventDialog}
						onConfirm={handleSaveEvent}
						onCancel={handleCancelAddEvent}
						loading={savingEvent}
					/>
				</div>
			</div>

			{/* Offer Details Section */}
			{showOfferCard && (
				<div data-testid="offer-details-section" className="mt-6">
					<OfferDetailsCard
						offerDetails={app.offer_details!}
						onEdit={handleEditOffer}
					/>
					<OfferDetailsDialog
						open={showOfferEditDialog}
						onConfirm={handleSaveOffer}
						onCancel={handleCancelOfferEdit}
						loading={savingOffer}
						initialData={app.offer_details}
					/>
				</div>
			)}

			{/* Rejection Details Section */}
			{showRejectionCard && (
				<div data-testid="rejection-details-section" className="mt-6">
					<RejectionDetailsCard
						rejectionDetails={app.rejection_details!}
						onEdit={handleEditRejection}
					/>
					<RejectionDetailsDialog
						open={showRejectionEditDialog}
						onConfirm={handleSaveRejection}
						onCancel={handleCancelRejectionEdit}
						loading={savingRejection}
						initialData={app.rejection_details}
					/>
				</div>
			)}

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
