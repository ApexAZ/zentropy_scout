"use client";

/**
 * Dashboard page — three-tab job management interface.
 *
 * REQ-012 §8.1: Opportunities, In Progress, and History tabs
 * with URL-persisted tab state.
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
