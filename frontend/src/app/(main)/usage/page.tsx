"use client";

/**
 * @fileoverview Usage dashboard page route.
 *
 * Layer: page
 * Feature: usage
 *
 * REQ-020 §9.2: Usage page at /usage showing balance,
 * period summary, cost breakdowns, and activity tables.
 *
 * Coordinates with:
 * - components/usage/usage-page.tsx: usage dashboard UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /usage
 */

import { UsagePage } from "@/components/usage/usage-page";
import { usePersonaStatus } from "@/hooks/use-persona-status";

/** Usage & billing page displaying metering data. */
export default function UsageRoute() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <UsagePage />;
}
