"use client";

/**
 * @fileoverview Three-tab dashboard layout with URL-persisted tab state.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-012 §8.1: Opportunities (scored, not applied), In Progress
 * (active applications), and History (terminal + archived) tabs.
 * Active tab is persisted in the URL as `?tab=<value>`.
 *
 * Coordinates with:
 * - components/dashboard/applications-table.tsx: In Progress and History tab content
 * - components/dashboard/opportunities-table.tsx: Opportunities tab content
 * - components/ui/tabs.tsx: Tabs, TabsContent, TabsList, TabsTrigger
 *
 * Called by / Used by:
 * - app/(main)/dashboard/page.tsx: dashboard page route
 */

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

import { PageTitle } from "@/components/ui/headings";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApplicationsTable } from "./applications-table";
import { OpportunitiesTable } from "./opportunities-table";

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

const VALID_TABS = ["opportunities", "in-progress", "history"] as const;
type DashboardTab = (typeof VALID_TABS)[number];

const TAB_OPPORTUNITIES: DashboardTab = "opportunities";
const TAB_IN_PROGRESS: DashboardTab = "in-progress";
const TAB_HISTORY: DashboardTab = "history";
const DEFAULT_TAB = TAB_OPPORTUNITIES;
const TAB_PARAM_KEY = "tab";

function isValidTab(value: string): value is DashboardTab {
	return (VALID_TABS as readonly string[]).includes(value);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DashboardTabs() {
	const searchParams = useSearchParams();
	const router = useRouter();

	const tabParam = searchParams.get(TAB_PARAM_KEY);
	const activeTab: DashboardTab =
		tabParam !== null && isValidTab(tabParam) ? tabParam : DEFAULT_TAB;

	const handleTabChange = useCallback(
		(value: string) => {
			if (!isValidTab(value)) return;

			const params = new URLSearchParams(searchParams.toString());

			if (value === DEFAULT_TAB) {
				params.delete(TAB_PARAM_KEY);
			} else {
				params.set(TAB_PARAM_KEY, value);
			}

			const query = params.toString();
			router.replace(query ? `/dashboard?${query}` : "/dashboard");
		},
		[searchParams, router],
	);

	return (
		<div data-testid="dashboard-tabs" className="flex flex-1 flex-col gap-6">
			<PageTitle>Dashboard</PageTitle>

			<Tabs value={activeTab} onValueChange={handleTabChange}>
				<TabsList>
					<TabsTrigger value={TAB_OPPORTUNITIES}>Opportunities</TabsTrigger>
					<TabsTrigger value={TAB_IN_PROGRESS}>In Progress</TabsTrigger>
					<TabsTrigger value={TAB_HISTORY}>History</TabsTrigger>
				</TabsList>

				<TabsContent value={TAB_OPPORTUNITIES}>
					<div data-testid="tab-content-opportunities" className="py-4">
						<OpportunitiesTable />
					</div>
				</TabsContent>

				<TabsContent value={TAB_IN_PROGRESS}>
					<div data-testid="tab-content-in-progress" className="py-4">
						<ApplicationsTable variant="in-progress" />
					</div>
				</TabsContent>

				<TabsContent value={TAB_HISTORY}>
					<div data-testid="tab-content-history" className="py-4">
						<ApplicationsTable variant="history" />
					</div>
				</TabsContent>
			</Tabs>
		</div>
	);
}
