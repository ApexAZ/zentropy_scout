"use client";

/**
 * Persona overview page component (§6.1).
 *
 * REQ-012 §7.1: Dashboard showing persona header, 8-card section grid
 * with counts and edit links, and a Discovery Preferences block.
 * Each card links to its section editor (§6.3–§6.14).
 */

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";

import { apiGet } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type {
	AchievementStory,
	Certification,
	CustomNonNegotiable,
	Education,
	Persona,
	Skill,
	VoiceProfile,
	WorkHistory,
} from "@/types/persona";

import { ChangeFlagsBanner } from "./change-flags-banner";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SectionCardDef {
	key: string;
	title: string;
	editHref: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTION_CARDS: readonly SectionCardDef[] = [
	{
		key: "work-history",
		title: "Work History",
		editHref: "/persona/work-history",
	},
	{ key: "skills", title: "Skills", editHref: "/persona/skills" },
	{
		key: "achievement-stories",
		title: "Stories",
		editHref: "/persona/achievement-stories",
	},
	{
		key: "certifications",
		title: "Certifications",
		editHref: "/persona/certifications",
	},
	{ key: "education", title: "Education", editHref: "/persona/education" },
	{ key: "voice", title: "Voice Profile", editHref: "/persona/voice" },
	{
		key: "non-negotiables",
		title: "Non-Negotiables",
		editHref: "/persona/non-negotiables",
	},
	{ key: "growth", title: "Growth Targets", editHref: "/persona/growth" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Pluralize a count with a label (e.g., 2 "position" -> "2 positions"). */
function pluralize(count: number, singular: string, plural?: string): string {
	return `${count} ${count === 1 ? singular : (plural ?? `${singular}s`)}`;
}

/** Check if a voice profile response has meaningful data. */
function isVoiceProfile(data: unknown): data is VoiceProfile {
	return data != null && typeof data === "object" && "tone" in data;
}

const SAFE_URL_PROTOCOLS = new Set(["https:", "http:"]);

/** Defense-in-depth: only render links with safe URL schemes. */
function isSafeUrl(url: string): boolean {
	try {
		return SAFE_URL_PROTOCOLS.has(new URL(url).protocol);
	} catch {
		return false;
	}
}

// ---------------------------------------------------------------------------
// PersonaHeader sub-component
// ---------------------------------------------------------------------------

function PersonaHeader({ persona }: { persona: Persona }) {
	const location = [persona.home_city, persona.home_state, persona.home_country]
		.filter(Boolean)
		.join(", ");

	return (
		<div
			className="grid grid-cols-1 gap-6 rounded-lg border p-6 md:grid-cols-2"
			data-testid="persona-header"
		>
			{/* Left column: identity */}
			<div className="space-y-1">
				<div className="flex items-center justify-between">
					<h2 className="text-lg font-semibold">{persona.full_name}</h2>
					<Link
						href="/persona/basic-info"
						className="text-primary text-xs font-medium hover:underline"
					>
						Edit
					</Link>
				</div>
				<p className="text-muted-foreground text-sm">{persona.email}</p>
				<p className="text-muted-foreground text-sm">{persona.phone}</p>
				<p className="text-muted-foreground text-sm">{location}</p>
				{persona.linkedin_url && isSafeUrl(persona.linkedin_url) && (
					<a
						href={persona.linkedin_url}
						className="text-primary text-sm hover:underline"
						target="_blank"
						rel="noopener noreferrer"
					>
						LinkedIn
					</a>
				)}
				{persona.portfolio_url && isSafeUrl(persona.portfolio_url) && (
					<a
						href={persona.portfolio_url}
						className="text-primary ml-3 text-sm hover:underline"
						target="_blank"
						rel="noopener noreferrer"
					>
						Portfolio
					</a>
				)}
			</div>

			{/* Right column: professional overview */}
			<div className="space-y-1">
				{persona.current_role && (
					<p className="text-sm font-medium">{persona.current_role}</p>
				)}
				{persona.current_company && (
					<p className="text-muted-foreground text-sm">
						{persona.current_company}
					</p>
				)}
				{persona.years_experience != null && (
					<p className="text-muted-foreground text-sm">
						{persona.years_experience} years
					</p>
				)}
				{persona.professional_summary && (
					<p className="text-muted-foreground mt-2 text-sm">
						{persona.professional_summary}
					</p>
				)}
			</div>
		</div>
	);
}

// ---------------------------------------------------------------------------
// SectionCard sub-component
// ---------------------------------------------------------------------------

function SectionCard({
	sectionKey,
	title,
	summary,
	editHref,
}: {
	sectionKey: string;
	title: string;
	summary: string;
	editHref: string;
}) {
	return (
		<div
			className="flex flex-col justify-between rounded-lg border p-4"
			data-testid={`section-card-${sectionKey}`}
		>
			<div>
				<h3 className="text-sm font-semibold">{title}</h3>
				<p className="text-muted-foreground mt-1 text-sm">{summary}</p>
			</div>
			<Link
				href={editHref}
				className="text-primary mt-3 text-xs font-medium hover:underline"
			>
				Edit
			</Link>
		</div>
	);
}

// ---------------------------------------------------------------------------
// DiscoveryPreferences sub-component
// ---------------------------------------------------------------------------

function DiscoveryPreferences({
	persona,
	editHref,
}: {
	persona: Persona;
	editHref: string;
}) {
	return (
		<div
			className="flex items-center justify-between rounded-lg border p-4"
			data-testid="discovery-preferences"
		>
			<div className="flex gap-6 text-sm">
				<div>
					<span className="text-muted-foreground">Fit threshold: </span>
					<span className="font-medium">{persona.minimum_fit_threshold}</span>
				</div>
				<div>
					<span className="text-muted-foreground">Auto-draft: </span>
					<span className="font-medium">{persona.auto_draft_threshold}</span>
				</div>
				<div>
					<span className="text-muted-foreground">Polling: </span>
					<span className="font-medium">{persona.polling_frequency}</span>
				</div>
			</div>
			<Link
				href={editHref}
				className="text-primary text-xs font-medium hover:underline"
			>
				Edit
			</Link>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * Persona overview page.
 *
 * Displays a two-column header with identity and professional info,
 * an 8-card grid with section counts and edit links, and a
 * Discovery Preferences block.
 */
export function PersonaOverview({ persona }: { persona: Persona }) {
	const personaId = persona.id;

	// Sub-entity queries (parallel, individually cached)
	const workHistoryQuery = useQuery({
		queryKey: queryKeys.workHistory(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<WorkHistory>>(
				`/personas/${personaId}/work-history`,
			),
	});

	const skillsQuery = useQuery({
		queryKey: queryKeys.skills(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<Skill>>(`/personas/${personaId}/skills`),
	});

	const educationQuery = useQuery({
		queryKey: queryKeys.education(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<Education>>(`/personas/${personaId}/education`),
	});

	const certificationsQuery = useQuery({
		queryKey: queryKeys.certifications(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<Certification>>(
				`/personas/${personaId}/certifications`,
			),
	});

	const storiesQuery = useQuery({
		queryKey: queryKeys.achievementStories(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<AchievementStory>>(
				`/personas/${personaId}/achievement-stories`,
			),
	});

	const voiceQuery = useQuery({
		queryKey: queryKeys.voiceProfile(personaId),
		queryFn: () =>
			apiGet<ApiResponse<VoiceProfile>>(`/personas/${personaId}/voice-profile`),
	});

	const nonNegQuery = useQuery({
		queryKey: queryKeys.customNonNegotiables(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<CustomNonNegotiable>>(
				`/personas/${personaId}/custom-non-negotiables`,
			),
	});

	// -----------------------------------------------------------------------
	// Loading state
	// -----------------------------------------------------------------------

	const isLoading =
		workHistoryQuery.isLoading ||
		skillsQuery.isLoading ||
		educationQuery.isLoading ||
		certificationsQuery.isLoading ||
		storiesQuery.isLoading ||
		voiceQuery.isLoading ||
		nonNegQuery.isLoading;

	if (isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-persona-overview"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">Loading your profile...</p>
			</div>
		);
	}

	// -----------------------------------------------------------------------
	// Build card summaries
	// -----------------------------------------------------------------------

	function getSummary(key: string): string {
		switch (key) {
			case "work-history": {
				const data = workHistoryQuery.data?.data;
				if (!data) return "—";
				return pluralize(data.length, "position");
			}
			case "skills": {
				const data = skillsQuery.data?.data;
				if (!data) return "—";
				const hard = data.filter((s) => s.skill_type === "Hard").length;
				const soft = data.filter((s) => s.skill_type === "Soft").length;
				return `${hard} Hard, ${soft} Soft`;
			}
			case "education": {
				const data = educationQuery.data?.data;
				if (!data) return "—";
				return pluralize(data.length, "entry", "entries");
			}
			case "certifications": {
				const data = certificationsQuery.data?.data;
				if (!data) return "—";
				return pluralize(data.length, "certification");
			}
			case "achievement-stories": {
				const data = storiesQuery.data?.data;
				if (!data) return "—";
				return pluralize(data.length, "story", "stories");
			}
			case "voice": {
				const vp = voiceQuery.data?.data;
				if (!vp || !isVoiceProfile(vp)) return "Not set";
				return "Configured";
			}
			case "non-negotiables": {
				const data = nonNegQuery.data?.data;
				if (!data) return "—";
				return pluralize(data.length, "custom filter");
			}
			case "growth": {
				const roles = persona.target_roles.length;
				const skills = persona.target_skills.length;
				return `${pluralize(roles, "target role")}, ${pluralize(skills, "target skill")}`;
			}
			default:
				return "—";
		}
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div className="flex flex-1 flex-col gap-6" data-testid="persona-overview">
			<h1 className="text-xl font-semibold">Your Professional Profile</h1>

			<PersonaHeader persona={persona} />

			<ChangeFlagsBanner />

			<div className="grid grid-cols-2 gap-4 md:grid-cols-4">
				{SECTION_CARDS.map((card) => (
					<SectionCard
						key={card.key}
						sectionKey={card.key}
						title={card.title}
						summary={getSummary(card.key)}
						editHref={card.editHref}
					/>
				))}
			</div>

			<DiscoveryPreferences persona={persona} editHref="/persona/discovery" />
		</div>
	);
}
