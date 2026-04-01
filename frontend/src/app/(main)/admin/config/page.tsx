"use client";

/**
 * @fileoverview Admin config page route.
 *
 * Layer: page
 * Feature: admin
 *
 * REQ-022 §11.1: Admin configuration dashboard at /admin/config.
 * Guards with useSession — redirects non-admin users.
 *
 * Coordinates with:
 * - components/admin/admin-config-page.tsx: admin dashboard UI component
 * - lib/auth-provider.tsx: useSession for admin role check
 *
 * Called by / Used by:
 * - Next.js framework: route /admin/config
 */

import { AdminConfigPage } from "@/components/admin/admin-config-page";
import { useSession } from "@/lib/auth-provider";

/** Admin config route — renders page only for admin users. */
export default function AdminConfigRoute() {
	const { session } = useSession();

	if (!session?.isAdmin) return null;

	return <AdminConfigPage />;
}
