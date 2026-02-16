/**
 * Connection status indicator with colored dot and label.
 *
 * REQ-012 §5.5: Reconnection UX — green/amber/red dot in chat header.
 * REQ-012 §13.8: prefers-reduced-motion respected for pulse animation.
 *
 * Accepts status as a prop rather than consuming useSSE() directly,
 * allowing the chat header to pass status down and keeping the
 * component testable without SSE context.
 */

import * as React from "react";

import type { ConnectionStatus as ConnectionStatusType } from "@/lib/sse-client";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ConnectionStatusProps {
	status: ConnectionStatusType;
	className?: string;
}

// ---------------------------------------------------------------------------
// Status configuration
// ---------------------------------------------------------------------------

const STATUS_CONFIG = {
	connected: {
		label: "Connected",
		ariaLabel: "Connected",
		dotClass: "bg-success",
		animate: false,
	},
	reconnecting: {
		label: "Reconnecting...",
		ariaLabel: "Reconnecting",
		dotClass: "bg-warning",
		animate: true,
	},
	disconnected: {
		label: "Disconnected",
		ariaLabel: "Disconnected",
		dotClass: "bg-destructive",
		animate: false,
	},
} as const satisfies Record<
	ConnectionStatusType,
	{ label: string; ariaLabel: string; dotClass: string; animate: boolean }
>;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function ConnectionStatus({
	status,
	className,
}: Readonly<ConnectionStatusProps>) {
	const config = STATUS_CONFIG[status];

	return (
		<div
			data-slot="connection-status"
			data-status={status}
			role="status"
			aria-live="polite"
			aria-label={`Connection status: ${config.ariaLabel}`}
			className={cn("flex items-center gap-1.5", className)}
		>
			<span
				data-slot="connection-status-dot"
				className={cn(
					"size-2 rounded-full",
					config.dotClass,
					config.animate && "motion-safe:animate-pulse",
				)}
			/>
			<span className="text-muted-foreground text-xs">{config.label}</span>
		</div>
	);
}

export { ConnectionStatus };
export type { ConnectionStatusProps };
