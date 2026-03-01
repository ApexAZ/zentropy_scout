"use client";

/**
 * Usage dashboard page route.
 *
 * REQ-020 §9.2: Usage page at /usage showing balance,
 * period summary, cost breakdowns, and activity tables.
 */

import { UsagePage } from "@/components/usage/usage-page";
import { usePersonaStatus } from "@/hooks/use-persona-status";

/** Usage & billing page displaying metering data. */
export default function UsageRoute() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <UsagePage />;
}
