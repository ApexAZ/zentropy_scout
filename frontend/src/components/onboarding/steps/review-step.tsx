"use client";

/**
 * Review step for onboarding wizard (Step 11).
 *
 * REQ-012 §6.3.11: Structured summary of the full persona in
 * collapsible sections. Each section has an "Edit" link that
 * navigates back to the relevant onboarding step. Read-only —
 * no form submission, only "Confirm and Continue" to advance.
 */

import { ArrowLeft, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { apiGet } from "@/lib/api-client";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type {
	AchievementStory,
	Certification,
	Education,
	Persona,
	Skill,
	VoiceProfile,
	WorkHistory,
} from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Metadata for a collapsible review section. */
interface SectionDef {
	key: string;
	title: string;
	editStep: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Section definitions mapping section keys to titles and edit step numbers. */
const SECTION_DEFS: readonly SectionDef[] = [
	{ key: "basic-info", title: "Basic Info", editStep: 2 },
	{ key: "professional-overview", title: "Professional Overview", editStep: 2 },
	{ key: "work-history", title: "Work History", editStep: 3 },
	{ key: "education", title: "Education", editStep: 4 },
	{ key: "skills", title: "Skills", editStep: 5 },
	{ key: "certifications", title: "Certifications", editStep: 6 },
	{ key: "achievement-stories", title: "Achievement Stories", editStep: 7 },
	{ key: "non-negotiables", title: "Non-Negotiables", editStep: 8 },
	{ key: "growth-targets", title: "Growth Targets", editStep: 9 },
	{ key: "voice-profile", title: "Voice Profile", editStep: 10 },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format a number as USD currency (e.g., 180000 → "$180,000"). */
function formatSalary(amount: number | null): string {
	if (amount == null) return "Not set";
	return new Intl.NumberFormat("en-US", {
		style: "currency",
		currency: "USD",
		minimumFractionDigits: 0,
		maximumFractionDigits: 0,
	}).format(amount);
}

/** Pluralize a count with a label (e.g., 2 "position" → "2 positions"). */
function pluralize(count: number, singular: string, plural?: string): string {
	return `${count} ${count === 1 ? singular : (plural ?? `${singular}s`)}`;
}

/** Check if a voice profile response has meaningful data. */
function isVoiceProfile(data: unknown): data is VoiceProfile {
	return data != null && typeof data === "object" && "tone" in data;
}

/** Placeholder for sections with no data. */
function NoDataPlaceholder() {
	return <p className="text-muted-foreground text-sm">No data</p>;
}

// ---------------------------------------------------------------------------
// CollapsibleSection sub-component
// ---------------------------------------------------------------------------

function CollapsibleSection({
	sectionKey,
	title,
	onEdit,
	children,
}: {
	sectionKey: string;
	title: string;
	onEdit: () => void;
	children: ReactNode;
}) {
	const [isOpen, setIsOpen] = useState(true);

	return (
		<div
			className="rounded-lg border"
			data-testid={`review-section-${sectionKey}`}
		>
			<button
				type="button"
				className="flex w-full items-center gap-2 p-3 text-left"
				onClick={() => setIsOpen(!isOpen)}
				data-testid={`review-header-${sectionKey}`}
			>
				{isOpen ? (
					<ChevronDown className="h-4 w-4 shrink-0" />
				) : (
					<ChevronRight className="h-4 w-4 shrink-0" />
				)}
				<span className="flex-1 text-sm font-semibold">{title}</span>
				<button
					type="button"
					className="text-primary text-xs font-medium hover:underline"
					onClick={(e) => {
						e.stopPropagation();
						onEdit();
					}}
					data-testid={`edit-${sectionKey}`}
				>
					Edit
				</button>
			</button>
			{isOpen && <div className="border-t px-3 pt-2 pb-3">{children}</div>}
		</div>
	);
}

// ---------------------------------------------------------------------------
// Section content renderers
// ---------------------------------------------------------------------------

/** Render a single labeled field row. */
function FieldRow({ label, value }: { label: string; value: ReactNode }) {
	return (
		<div className="flex gap-2 text-sm">
			<span className="text-muted-foreground w-24 shrink-0 font-medium">
				{label}
			</span>
			<span>{value || "Not provided"}</span>
		</div>
	);
}

function BasicInfoContent({ persona }: { persona: Persona | null }) {
	if (!persona) return <NoDataPlaceholder />;
	const location = [persona.home_city, persona.home_state, persona.home_country]
		.filter(Boolean)
		.join(", ");
	return (
		<div className="space-y-1">
			<FieldRow label="Name" value={persona.full_name} />
			<FieldRow label="Email" value={persona.email} />
			<FieldRow label="Phone" value={persona.phone} />
			<FieldRow label="Location" value={location} />
			{persona.linkedin_url && (
				<FieldRow label="LinkedIn" value={persona.linkedin_url} />
			)}
			{persona.portfolio_url && (
				<FieldRow label="Portfolio" value={persona.portfolio_url} />
			)}
		</div>
	);
}

function ProfessionalOverviewContent({ persona }: { persona: Persona | null }) {
	if (!persona) return <NoDataPlaceholder />;
	return (
		<div className="space-y-1">
			{persona.current_role && (
				<FieldRow label="Role" value={persona.current_role} />
			)}
			{persona.current_company && (
				<FieldRow label="Company" value={persona.current_company} />
			)}
			{persona.years_experience != null && (
				<FieldRow
					label="Experience"
					value={`${persona.years_experience} years`}
				/>
			)}
			{persona.professional_summary && (
				<FieldRow label="Summary" value={persona.professional_summary} />
			)}
		</div>
	);
}

function WorkHistoryContent({ items }: { items: WorkHistory[] }) {
	return <p className="text-sm">{pluralize(items.length, "position")}</p>;
}

function EducationContent({ items }: { items: Education[] }) {
	return (
		<p className="text-sm">{pluralize(items.length, "entry", "entries")}</p>
	);
}

function SkillsContent({ items }: { items: Skill[] }) {
	const hardCount = items.filter((s) => s.skill_type === "Hard").length;
	const softCount = items.filter((s) => s.skill_type === "Soft").length;
	return (
		<p className="text-sm">
			{hardCount} Hard, {softCount} Soft
		</p>
	);
}

function CertificationsContent({ items }: { items: Certification[] }) {
	return <p className="text-sm">{pluralize(items.length, "certification")}</p>;
}

function StoriesContent({ items }: { items: AchievementStory[] }) {
	return (
		<p className="text-sm">{pluralize(items.length, "story", "stories")}</p>
	);
}

function NonNegotiablesContent({ persona }: { persona: Persona | null }) {
	if (!persona) return <NoDataPlaceholder />;
	return (
		<div className="space-y-1">
			<FieldRow label="Remote" value={persona.remote_preference} />
			<FieldRow
				label="Min Salary"
				value={formatSalary(persona.minimum_base_salary)}
			/>
			<FieldRow label="Company Size" value={persona.company_size_preference} />
			<FieldRow label="Max Travel" value={persona.max_travel_percent} />
		</div>
	);
}

function GrowthTargetsContent({ persona }: { persona: Persona | null }) {
	if (!persona) return <NoDataPlaceholder />;
	return (
		<div className="space-y-2">
			{persona.target_roles.length > 0 && (
				<div>
					<span className="text-muted-foreground text-xs font-medium">
						Target Roles
					</span>
					<div className="mt-1 flex flex-wrap gap-1">
						{persona.target_roles.map((role) => (
							<span
								key={role}
								className="bg-secondary text-secondary-foreground rounded-md px-2 py-0.5 text-xs"
							>
								{role}
							</span>
						))}
					</div>
				</div>
			)}
			{persona.target_skills.length > 0 && (
				<div>
					<span className="text-muted-foreground text-xs font-medium">
						Target Skills
					</span>
					<div className="mt-1 flex flex-wrap gap-1">
						{persona.target_skills.map((skill) => (
							<span
								key={skill}
								className="bg-secondary text-secondary-foreground rounded-md px-2 py-0.5 text-xs"
							>
								{skill}
							</span>
						))}
					</div>
				</div>
			)}
			<FieldRow label="Stretch" value={persona.stretch_appetite} />
		</div>
	);
}

function VoiceProfileContent({ profile }: { profile: VoiceProfile | null }) {
	if (!profile?.tone) return <NoDataPlaceholder />;
	return (
		<div className="space-y-1">
			<FieldRow label="Tone" value={profile.tone} />
			<FieldRow label="Style" value={profile.sentence_style} />
			<FieldRow label="Vocabulary" value={profile.vocabulary_level} />
		</div>
	);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 11: Review.
 *
 * Displays a read-only summary of the full persona in collapsible sections.
 * Each section links back to its edit step. "Confirm and Continue" advances
 * to Step 12 (Base Resume Setup).
 */
export function ReviewStep() {
	const { personaId, next, back, goToStep } = useOnboarding();

	const [isLoading, setIsLoading] = useState(!!personaId);
	const [persona, setPersona] = useState<Persona | null>(null);
	const [workHistories, setWorkHistories] = useState<WorkHistory[]>([]);
	const [educations, setEducations] = useState<Education[]>([]);
	const [skills, setSkills] = useState<Skill[]>([]);
	const [certifications, setCertifications] = useState<Certification[]>([]);
	const [stories, setStories] = useState<AchievementStory[]>([]);
	const [voiceProfile, setVoiceProfile] = useState<VoiceProfile | null>(null);

	// -----------------------------------------------------------------------
	// Fetch all persona data on mount
	// -----------------------------------------------------------------------

	useEffect(() => {
		if (!personaId) return;

		let cancelled = false;

		Promise.all([
			apiGet<ApiListResponse<Persona>>("/personas"),
			apiGet<ApiListResponse<WorkHistory>>(
				`/personas/${personaId}/work-history`,
			),
			apiGet<ApiListResponse<Education>>(`/personas/${personaId}/education`),
			apiGet<ApiListResponse<Skill>>(`/personas/${personaId}/skills`),
			apiGet<ApiListResponse<Certification>>(
				`/personas/${personaId}/certifications`,
			),
			apiGet<ApiListResponse<AchievementStory>>(
				`/personas/${personaId}/achievement-stories`,
			),
			apiGet<ApiResponse<VoiceProfile>>(`/personas/${personaId}/voice-profile`),
		])
			.then(
				([personaRes, whRes, eduRes, skillRes, certRes, storyRes, vpRes]) => {
					if (cancelled) return;
					setPersona(personaRes.data[0] ?? null);
					setWorkHistories(whRes.data);
					setEducations(eduRes.data);
					setSkills(skillRes.data);
					setCertifications(certRes.data);
					setStories(storyRes.data);
					const vp = vpRes.data;
					setVoiceProfile(isVoiceProfile(vp) ? vp : null);
				},
			)
			.catch(() => {
				// Fetch failed — show empty review
			})
			.finally(() => {
				if (!cancelled) setIsLoading(false);
			});

		return () => {
			cancelled = true;
		};
	}, [personaId]);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleConfirm = useCallback(() => {
		next();
	}, [next]);

	// -----------------------------------------------------------------------
	// Render helpers
	// -----------------------------------------------------------------------

	function renderSectionContent(key: string): ReactNode {
		switch (key) {
			case "basic-info":
				return <BasicInfoContent persona={persona} />;
			case "professional-overview":
				return <ProfessionalOverviewContent persona={persona} />;
			case "work-history":
				return <WorkHistoryContent items={workHistories} />;
			case "education":
				return <EducationContent items={educations} />;
			case "skills":
				return <SkillsContent items={skills} />;
			case "certifications":
				return <CertificationsContent items={certifications} />;
			case "achievement-stories":
				return <StoriesContent items={stories} />;
			case "non-negotiables":
				return <NonNegotiablesContent persona={persona} />;
			case "growth-targets":
				return <GrowthTargetsContent persona={persona} />;
			case "voice-profile":
				return <VoiceProfileContent profile={voiceProfile} />;
			default:
				return null;
		}
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-review"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">Loading your review...</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div className="text-center">
				<h2 className="text-lg font-semibold">Review</h2>
				<p className="text-muted-foreground mt-1">
					Everything look good? Review your persona below.
				</p>
			</div>

			<div className="space-y-3">
				{SECTION_DEFS.map(({ key, title, editStep }) => (
					<CollapsibleSection
						key={key}
						sectionKey={key}
						title={title}
						onEdit={() => goToStep(editStep)}
					>
						{renderSectionContent(key)}
					</CollapsibleSection>
				))}
			</div>

			{/* Navigation */}
			<div className="flex items-center justify-between pt-4">
				<Button
					type="button"
					variant="ghost"
					onClick={back}
					data-testid="back-button"
				>
					<ArrowLeft className="mr-2 h-4 w-4" />
					Back
				</Button>
				<Button
					type="button"
					onClick={handleConfirm}
					data-testid="confirm-button"
				>
					Confirm and Continue
				</Button>
			</div>
		</div>
	);
}
