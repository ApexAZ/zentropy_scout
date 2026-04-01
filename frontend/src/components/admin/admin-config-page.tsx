"use client";

/**
 * @fileoverview Admin configuration page with tabbed navigation.
 *
 * Layer: component
 * Feature: admin
 *
 * REQ-022 §11.1-§11.2: Single page with 6 tabs — Models, Pricing,
 * Routing, Packs, System, Users. Each tab delegates to its own
 * component for CRUD operations.
 *
 * Coordinates with:
 * - components/ui/tabs.tsx: Tabs, TabsContent, TabsList, TabsTrigger for tab navigation
 * - components/admin/models-tab.tsx: ModelsTab for model registry management
 * - components/admin/packs-tab.tsx: PacksTab for funding pack management
 * - components/admin/pricing-tab.tsx: PricingTab for pricing config management
 * - components/admin/routing-tab.tsx: RoutingTab for task routing management
 * - components/admin/system-tab.tsx: SystemTab for system config management
 * - components/admin/users-tab.tsx: UsersTab for user admin management
 *
 * Called by / Used by:
 * - app/(main)/admin/config/page.tsx: admin configuration route page
 */

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { ModelsTab } from "./models-tab";
import { PacksTab } from "./packs-tab";
import { PricingTab } from "./pricing-tab";
import { RoutingTab } from "./routing-tab";
import { SystemTab } from "./system-tab";
import { UsersTab } from "./users-tab";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Admin config page with 6 management tabs. */
export function AdminConfigPage() {
	return (
		<div data-testid="admin-config-page" className="space-y-6">
			<h1 className="text-2xl font-bold">Admin Configuration</h1>

			<Tabs defaultValue="models">
				<TabsList>
					<TabsTrigger value="models">Models</TabsTrigger>
					<TabsTrigger value="pricing">Pricing</TabsTrigger>
					<TabsTrigger value="routing">Routing</TabsTrigger>
					<TabsTrigger value="packs">Packs</TabsTrigger>
					<TabsTrigger value="system">System</TabsTrigger>
					<TabsTrigger value="users">Users</TabsTrigger>
				</TabsList>

				<TabsContent value="models">
					<ModelsTab />
				</TabsContent>
				<TabsContent value="pricing">
					<PricingTab />
				</TabsContent>
				<TabsContent value="routing">
					<RoutingTab />
				</TabsContent>
				<TabsContent value="packs">
					<PacksTab />
				</TabsContent>
				<TabsContent value="system">
					<SystemTab />
				</TabsContent>
				<TabsContent value="users">
					<UsersTab />
				</TabsContent>
			</Tabs>
		</div>
	);
}
