import * as React from "react";
import { CircleAlert, FileQuestion, Inbox, RefreshCw } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const stateLayoutClasses =
	"flex flex-col items-center justify-center gap-4 py-12 text-center";
const stateTitleClasses = "text-lg font-semibold";
const mutedIconClasses = "text-muted-foreground size-12";

interface EmptyStateProps extends React.ComponentProps<"div"> {
	icon?: React.ComponentType<{ className?: string }>;
	title: string;
	description?: string;
	action?: {
		label: string;
		onClick: () => void;
	};
}

interface FailedStateProps extends React.ComponentProps<"div"> {
	/** User-facing error message. Must NOT contain raw server errors or stack traces. */
	message?: string;
	/** Application error code (e.g., "NETWORK_ERROR"). Must NOT contain internal details. */
	errorCode?: string;
	onRetry?: () => void;
}

interface NotFoundStateProps extends React.ComponentProps<"div"> {
	itemType?: string;
	onBack?: () => void;
}

interface ConflictStateProps extends React.ComponentProps<"div"> {
	message?: string;
	onRefresh?: () => void;
}

function EmptyState({
	icon: Icon = Inbox,
	title,
	description,
	action,
	className,
	...props
}: Readonly<EmptyStateProps>) {
	return (
		<div
			data-slot="empty-state"
			role="status"
			className={cn(stateLayoutClasses, className)}
			{...props}
		>
			<Icon className={mutedIconClasses} />
			<div className="space-y-1">
				<p className={stateTitleClasses}>{title}</p>
				{description && (
					<p className="text-muted-foreground text-sm">{description}</p>
				)}
			</div>
			{action && <Button onClick={action.onClick}>{action.label}</Button>}
		</div>
	);
}

function FailedState({
	message = "Failed to load.",
	errorCode,
	onRetry,
	className,
	...props
}: Readonly<FailedStateProps>) {
	return (
		<div
			data-slot="failed-state"
			role="alert"
			className={cn(stateLayoutClasses, className)}
			{...props}
		>
			<CircleAlert className="text-destructive size-12" />
			<div className="space-y-1">
				<p className={stateTitleClasses}>{message}</p>
				{errorCode && (
					<p className="text-muted-foreground font-mono text-sm">{errorCode}</p>
				)}
			</div>
			{onRetry && (
				<Button variant="outline" size="sm" onClick={onRetry}>
					Retry
				</Button>
			)}
		</div>
	);
}

function NotFoundState({
	itemType = "item",
	onBack,
	className,
	...props
}: Readonly<NotFoundStateProps>) {
	return (
		<div
			data-slot="not-found-state"
			role="alert"
			className={cn(stateLayoutClasses, className)}
			{...props}
		>
			<FileQuestion className={mutedIconClasses} />
			<p className={stateTitleClasses}>This {itemType} doesn&rsquo;t exist.</p>
			{onBack && (
				<Button variant="outline" size="sm" onClick={onBack}>
					Go back
				</Button>
			)}
		</div>
	);
}

function ConflictState({
	message = "This was modified.",
	onRefresh,
	className,
	...props
}: Readonly<ConflictStateProps>) {
	return (
		<div
			data-slot="conflict-state"
			role="alert"
			className={cn(stateLayoutClasses, className)}
			{...props}
		>
			<RefreshCw className={mutedIconClasses} />
			<p className={stateTitleClasses}>{message}</p>
			{onRefresh && (
				<Button variant="outline" size="sm" onClick={onRefresh}>
					Refresh
				</Button>
			)}
		</div>
	);
}

export { EmptyState, FailedState, NotFoundState, ConflictState };
export type {
	EmptyStateProps,
	FailedStateProps,
	NotFoundStateProps,
	ConflictStateProps,
};
