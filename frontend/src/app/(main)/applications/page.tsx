"use client";

/**
 * @fileoverview Applications list page route.
 *
 * Layer: page
 * Feature: applications
 *
 * REQ-012 §11.1: Dedicated application tracking page with
 * full table, toolbar, multi-select, and bulk archive.
 *
 * Coordinates with:
 * - components/applications/applications-list.tsx: applications table UI
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /applications
 */

import { usePersonaStatus } from "@/hooks/use-persona-status";
import { ApplicationsList } from "@/components/applications/applications-list";

/** Applications page displaying all tracked job applications. */
export default function ApplicationsPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <ApplicationsList />;
}
