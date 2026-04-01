"use client";

/**
 * @fileoverview Application detail page route.
 *
 * Layer: page
 * Feature: applications
 *
 * REQ-012 §11.2: Application detail page with header,
 * documents panel, notes section, and timeline.
 *
 * Coordinates with:
 * - components/applications/application-detail.tsx: detail UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /applications/[id]
 */

import { useParams } from "next/navigation";

import { usePersonaStatus } from "@/hooks/use-persona-status";
import { ApplicationDetail } from "@/components/applications/application-detail";

/** Application detail page displaying header, documents, and notes. */
export default function ApplicationDetailPage() {
	const personaStatus = usePersonaStatus();
	const params = useParams<{ id: string }>();

	if (personaStatus.status !== "onboarded") return null;

	return <ApplicationDetail applicationId={params.id} />;
}
