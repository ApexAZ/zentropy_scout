"use client";

/**
 * Admin config page route.
 *
 * REQ-022 §11.1: Admin configuration dashboard at /admin/config.
 * Guards with useSession — redirects non-admin users.
 */

import { AdminConfigPage } from "@/components/admin/admin-config-page";
import { useSession } from "@/lib/auth-provider";

/** Admin config route — renders page only for admin users. */
export default function AdminConfigRoute() {
	const { session } = useSession();

	if (!session?.isAdmin) return null;

	return <AdminConfigPage />;
}
