"use client";

/**
 * Vertical chronological timeline displaying application events.
 *
 * REQ-012 §11.7: Timeline with event type icons, immutable events,
 * and "Add Event" button for manual entries.
 */

import { useQuery } from "@tanstack/react-query";
import {
	Calendar,
	CheckCircle,
	FileText,
	Gift,
	Loader2,
	Mail,
	MailOpen,
	MessageSquare,
	Plus,
	RefreshCw,
	Send,
	Trophy,
	Undo2,
	XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { apiGet } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FailedState } from "@/components/ui/error-states";
import type { ApiListResponse } from "@/types/api";
import type { TimelineEvent, TimelineEventType } from "@/types/application";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

interface EventTypeConfig {
	icon: LucideIcon;
	label: string;
}

const EVENT_TYPE_MAP: Record<TimelineEventType, EventTypeConfig> = {
	applied: { icon: Send, label: "Applied" },
	status_changed: { icon: RefreshCw, label: "Status Changed" },
	note_added: { icon: FileText, label: "Note Added" },
	interview_scheduled: { icon: Calendar, label: "Interview Scheduled" },
	interview_completed: { icon: CheckCircle, label: "Interview Completed" },
	offer_received: { icon: Gift, label: "Offer Received" },
	offer_accepted: { icon: Trophy, label: "Offer Accepted" },
	rejected: { icon: XCircle, label: "Rejected" },
	withdrawn: { icon: Undo2, label: "Withdrawn" },
	follow_up_sent: { icon: Mail, label: "Follow-up Sent" },
	response_received: { icon: MailOpen, label: "Response Received" },
	custom: { icon: MessageSquare, label: "Custom Event" },
};

const FALLBACK_CONFIG: EventTypeConfig = {
	icon: MessageSquare,
	label: "Event",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ApplicationTimelineProps {
	applicationId: string;
	onAddEvent?: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatEventDate(isoString: string): string {
	const date = new Date(isoString);
	if (Number.isNaN(date.getTime())) return "Unknown";
	return date.toLocaleDateString("en-US", {
		month: "short",
		day: "numeric",
		year: "numeric",
		timeZone: "UTC",
	});
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ApplicationTimeline({
	applicationId,
	onAddEvent,
}: Readonly<ApplicationTimelineProps>) {
	const { data, isLoading, error, refetch } = useQuery({
		queryKey: queryKeys.timelineEvents(applicationId),
		queryFn: () =>
			apiGet<ApiListResponse<TimelineEvent>>(
				`/applications/${applicationId}/timeline`,
			),
	});

	// Loading
	if (isLoading) {
		return (
			<div data-testid="timeline-loading" className="flex justify-center py-8">
				<Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
			</div>
		);
	}

	// Error
	if (error) {
		return <FailedState onRetry={() => refetch()} />;
	}

	const events = data?.data ?? [];

	return (
		<Card data-testid="application-timeline">
			<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
				<CardTitle className="text-base">Timeline</CardTitle>
				{onAddEvent && (
					<Button
						variant="outline"
						size="sm"
						onClick={onAddEvent}
						className="gap-1"
					>
						<Plus className="h-3.5 w-3.5" />
						Add Event
					</Button>
				)}
			</CardHeader>
			<CardContent>
				{events.length === 0 ? (
					<p
						data-testid="timeline-empty"
						className="text-muted-foreground py-4 text-center text-sm"
					>
						No events yet.
					</p>
				) : (
					<div className="relative space-y-0">
						{events.map((event, index) => {
							const config =
								EVENT_TYPE_MAP[event.event_type] ?? FALLBACK_CONFIG;
							const Icon = config.icon;
							const isLast = index === events.length - 1;

							return (
								<div
									key={event.id}
									data-testid="timeline-event-item"
									className="relative flex gap-3 pb-6 last:pb-0"
								>
									{/* Vertical line */}
									{!isLast && (
										<div className="bg-border absolute top-8 bottom-0 left-[15px] w-px" />
									)}

									{/* Icon */}
									<div
										data-testid={`timeline-icon-${event.event_type}`}
										className="bg-muted text-muted-foreground z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
									>
										<Icon className="h-4 w-4" />
									</div>

									{/* Content */}
									<div className="min-w-0 flex-1 pt-0.5">
										<div className="flex items-baseline gap-2">
											<span className="text-sm font-medium">
												{config.label}
											</span>
											{event.interview_stage && (
												<span
													data-testid="timeline-event-stage"
													className="bg-warning/20 text-warning-foreground inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
												>
													{event.interview_stage}
												</span>
											)}
										</div>
										<p className="text-muted-foreground text-xs">
											{formatEventDate(event.event_date)}
										</p>
										{event.description && (
											<p
												data-testid="timeline-event-description"
												className="mt-1 text-sm"
											>
												{event.description}
											</p>
										)}
									</div>
								</div>
							);
						})}
					</div>
				)}
			</CardContent>
		</Card>
	);
}
