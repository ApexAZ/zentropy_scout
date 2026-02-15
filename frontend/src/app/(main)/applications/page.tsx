"use client";

/**
 * Applications page route.
 *
 * REQ-012 §11.1: Dedicated application tracking page with
 * full table, toolbar, multi-select, and bulk archive.
 */

import { usePersonaStatus } from "@/hooks/use-persona-status";
import { ApplicationsList } from "@/components/applications/applications-list";

/** Applications page displaying all tracked job applications. */
export default function ApplicationsPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <ApplicationsList />;
}
