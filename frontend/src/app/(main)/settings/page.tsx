"use client";

/**
 * @fileoverview Settings page route.
 *
 * Layer: page
 * Feature: shared
 *
 * REQ-012 §12.1: Settings and configuration page with
 * job source preferences, agent config, and about section.
 *
 * Coordinates with:
 * - components/settings/settings-page.tsx: settings UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /settings
 */

import { usePersonaStatus } from "@/hooks/use-persona-status";
import { SettingsPage } from "@/components/settings/settings-page";

/** Settings page displaying configuration options. */
export default function SettingsRoute() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <SettingsPage personaId={personaStatus.persona.id} />;
}
