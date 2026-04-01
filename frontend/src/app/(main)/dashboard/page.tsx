"use client";

/**
 * @fileoverview Dashboard page — three-tab job management interface.
 *
 * Layer: page
 * Feature: jobs
 *
 * REQ-012 §8.1: Opportunities, In Progress, and History tabs
 * with URL-persisted tab state.
 *
 * Coordinates with:
 * - components/dashboard/dashboard-tabs.tsx: tabbed job list UI
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /dashboard
 */

import { Suspense } from "react";

import { DashboardTabs } from "@/components/dashboard/dashboard-tabs";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function DashboardPage() {
	const personaStatus = usePersonaStatus();
	if (personaStatus.status !== "onboarded") return null;

	return (
		<Suspense>
			<DashboardTabs />
		</Suspense>
	);
}
