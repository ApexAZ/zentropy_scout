"use client";

/**
 * Settings page route.
 *
 * REQ-012 §12.1: Settings & configuration page with
 * job source preferences, agent config, and about section.
 */

import { usePersonaStatus } from "@/hooks/use-persona-status";
import { SettingsPage } from "@/components/settings/settings-page";

/** Settings page displaying configuration options. */
export default function SettingsRoute() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <SettingsPage personaId={personaStatus.persona.id} />;
}
