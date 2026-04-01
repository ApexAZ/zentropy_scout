"use client";

/**
 * @fileoverview PersonaChangeFlags resolution page route.
 *
 * Layer: page
 * Feature: persona
 *
 * REQ-012 §7.6: Review and resolve pending change flags
 * (add to all resumes, add to some, or skip). Only rendered
 * for onboarded users.
 *
 * Coordinates with:
 * - components/persona/change-flags-resolver.tsx: resolver UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /persona/change-flags
 */

import { ChangeFlagsResolver } from "@/components/persona/change-flags-resolver";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function ChangeFlagsPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <ChangeFlagsResolver />;
}
