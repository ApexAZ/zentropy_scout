/**
 * Persona domain types matching backend/app/models/persona*.py.
 *
 * REQ-001: Professional persona data model.
 * REQ-005 §4.1: Database schema (Tier 1 Persona, Tier 2 sub-entities).
 * REQ-012 §4: Frontend architecture.
 */

// ---------------------------------------------------------------------------
// Enum union types — match backend CHECK constraints
// ---------------------------------------------------------------------------

/** Backend: WorkHistory.work_model CHECK constraint. */
export type WorkModel = "Remote" | "Hybrid" | "Onsite";

/** Backend: Skill.skill_type CHECK constraint. */
export type SkillType = "Hard" | "Soft";

/** Backend: Skill.proficiency CHECK constraint. Ordered ascending. */
export type Proficiency = "Learning" | "Familiar" | "Proficient" | "Expert";

/** Backend: Persona.remote_preference CHECK constraint. */
export type RemotePreference =
	| "Remote Only"
	| "Hybrid OK"
	| "Onsite OK"
	| "No Preference";

/** Backend: Persona.company_size_preference CHECK constraint. */
export type CompanySizePreference =
	| "Startup"
	| "Mid-size"
	| "Enterprise"
	| "No Preference";

/** Backend: Persona.max_travel_percent CHECK constraint. */
export type MaxTravelPercent = "None" | "<25%" | "<50%" | "Any";

/** Backend: Persona.stretch_appetite CHECK constraint. */
export type StretchAppetite = "Low" | "Medium" | "High";

/** Backend: Persona.polling_frequency CHECK constraint. */
export type PollingFrequency =
	| "Daily"
	| "Twice Daily"
	| "Weekly"
	| "Manual Only";

/** Backend: CustomNonNegotiable.filter_type CHECK constraint. */
export type FilterType = "Exclude" | "Require";

/** Backend: PersonaChangeFlag.change_type CHECK constraint. */
export type ChangeType =
	| "job_added"
	| "bullet_added"
	| "skill_added"
	| "education_added"
	| "certification_added";

/** Backend: PersonaChangeFlag.status CHECK constraint. */
export type ChangeFlagStatus = "Pending" | "Resolved";

/** Backend: PersonaChangeFlag.resolution CHECK constraint. */
export type ChangeFlagResolution = "added_to_all" | "added_to_some" | "skipped";

// ---------------------------------------------------------------------------
// Enum value arrays — for form dropdowns and validation
// ---------------------------------------------------------------------------

export const WORK_MODELS: readonly WorkModel[] = [
	"Remote",
	"Hybrid",
	"Onsite",
] as const;

export const PROFICIENCIES: readonly Proficiency[] = [
	"Learning",
	"Familiar",
	"Proficient",
	"Expert",
] as const;

export const REMOTE_PREFERENCES: readonly RemotePreference[] = [
	"Remote Only",
	"Hybrid OK",
	"Onsite OK",
	"No Preference",
] as const;

export const COMPANY_SIZE_PREFERENCES: readonly CompanySizePreference[] = [
	"Startup",
	"Mid-size",
	"Enterprise",
	"No Preference",
] as const;

export const MAX_TRAVEL_PERCENTS: readonly MaxTravelPercent[] = [
	"None",
	"<25%",
	"<50%",
	"Any",
] as const;

export const STRETCH_APPETITES: readonly StretchAppetite[] = [
	"Low",
	"Medium",
	"High",
] as const;

export const POLLING_FREQUENCIES: readonly PollingFrequency[] = [
	"Daily",
	"Twice Daily",
	"Weekly",
	"Manual Only",
] as const;

export const FILTER_TYPES: readonly FilterType[] = [
	"Exclude",
	"Require",
] as const;

export const CHANGE_TYPES: readonly ChangeType[] = [
	"job_added",
	"bullet_added",
	"skill_added",
	"education_added",
	"certification_added",
] as const;

export const CHANGE_FLAG_STATUSES: readonly ChangeFlagStatus[] = [
	"Pending",
	"Resolved",
] as const;

export const CHANGE_FLAG_RESOLUTIONS: readonly ChangeFlagResolution[] = [
	"added_to_all",
	"added_to_some",
	"skipped",
] as const;

// ---------------------------------------------------------------------------
// Sub-entity interfaces — Tier 2 & 3 models
// ---------------------------------------------------------------------------

/**
 * Accomplishment bullet within a work history entry.
 *
 * Backend: Bullet model (persona_content.py). Tier 3 — references WorkHistory.
 */
export interface Bullet {
	id: string;
	work_history_id: string;
	text: string;
	/** UUID references to Skill entities. */
	skills_demonstrated: string[];
	metrics: string | null;
	display_order: number;
}

/**
 * Work history entry with nested accomplishment bullets.
 *
 * Backend: WorkHistory model (persona_content.py). Tier 2 — references Persona.
 */
export interface WorkHistory {
	id: string;
	persona_id: string;
	company_name: string;
	company_industry: string | null;
	job_title: string;
	/** ISO date string (YYYY-MM-DD). */
	start_date: string;
	/** ISO date string. Null when is_current is true. */
	end_date: string | null;
	is_current: boolean;
	location: string;
	work_model: WorkModel;
	description: string | null;
	display_order: number;
	bullets: Bullet[];
}

/**
 * Skill entry — hard or soft.
 *
 * Backend: Skill model (persona_content.py). Tier 2 — references Persona.
 * Unique constraint: (persona_id, skill_name).
 */
export interface Skill {
	id: string;
	persona_id: string;
	skill_name: string;
	skill_type: SkillType;
	category: string;
	proficiency: Proficiency;
	years_used: number;
	/** "Current" or a year string (e.g., "2023"). */
	last_used: string;
	display_order: number;
}

/**
 * Education entry.
 *
 * Backend: Education model (persona_content.py). Tier 2 — references Persona.
 */
export interface Education {
	id: string;
	persona_id: string;
	institution: string;
	degree: string;
	field_of_study: string;
	graduation_year: number;
	/** Decimal GPA (0.00–4.00). Null if not provided. */
	gpa: number | null;
	honors: string | null;
	display_order: number;
}

/**
 * Professional certification.
 *
 * Backend: Certification model (persona_content.py). Tier 2 — references Persona.
 */
export interface Certification {
	id: string;
	persona_id: string;
	certification_name: string;
	issuing_organization: string;
	/** ISO date string. */
	date_obtained: string;
	/** ISO date string. Null means no expiration. */
	expiration_date: string | null;
	credential_id: string | null;
	verification_url: string | null;
	display_order: number;
}

/**
 * Achievement story in Context–Action–Outcome (CAO/STAR) format.
 *
 * Backend: AchievementStory model (persona_content.py). Tier 2 — references Persona.
 */
export interface AchievementStory {
	id: string;
	persona_id: string;
	title: string;
	/** 1-2 sentences describing the situation. */
	context: string;
	action: string;
	outcome: string;
	/** UUID references to Skill entities. */
	skills_demonstrated: string[];
	/** UUID reference to WorkHistory. Null if unlinked. */
	related_job_id: string | null;
	display_order: number;
}

/**
 * Writing voice preferences for content generation.
 *
 * Backend: VoiceProfile model (persona_settings.py). One-to-one with Persona.
 */
export interface VoiceProfile {
	id: string;
	persona_id: string;
	tone: string;
	sentence_style: string;
	vocabulary_level: string;
	personality_markers: string | null;
	sample_phrases: string[];
	/** Words/phrases to avoid in generated content. */
	things_to_avoid: string[];
	writing_sample_text: string | null;
	created_at: string;
	updated_at: string;
}

/**
 * User-defined filter rule for job matching.
 *
 * Backend: CustomNonNegotiable model (persona_settings.py). Tier 2 — references Persona.
 */
export interface CustomNonNegotiable {
	id: string;
	persona_id: string;
	filter_name: string;
	filter_type: FilterType;
	filter_value: string;
	/** Job field to check (e.g., "company_name", "description", "job_title"). */
	filter_field: string;
}

/**
 * Tracks persona changes needing HITL review for base resume updates.
 *
 * Backend: PersonaChangeFlag model (persona_settings.py). Tier 2 — references Persona.
 */
export interface PersonaChangeFlag {
	id: string;
	persona_id: string;
	change_type: ChangeType;
	item_id: string;
	item_description: string;
	status: ChangeFlagStatus;
	resolution: ChangeFlagResolution | null;
	/** ISO 8601 datetime. Null when status is Pending. */
	resolved_at: string | null;
	created_at: string;
}

// ---------------------------------------------------------------------------
// Main Persona interface — Tier 1 model
// ---------------------------------------------------------------------------

/**
 * User's professional persona — the core domain entity.
 *
 * Backend: Persona model (persona.py). Tier 1 — references User.
 * Sub-entities (WorkHistory, Skills, etc.) are fetched via separate endpoints.
 */
export interface Persona {
	id: string;
	user_id: string;

	// Basic Info (REQ-001 §3.1)
	full_name: string;
	email: string;
	phone: string;
	home_city: string;
	home_state: string;
	home_country: string;
	linkedin_url: string | null;
	portfolio_url: string | null;

	// Professional Overview (REQ-001 §3.1b)
	professional_summary: string | null;
	years_experience: number | null;
	current_role: string | null;
	current_company: string | null;

	// Growth Targets (REQ-001 §3.9)
	target_roles: string[];
	target_skills: string[];
	stretch_appetite: StretchAppetite;

	// Non-Negotiables: Location (REQ-001 §3.8.1)
	commutable_cities: string[];
	max_commute_minutes: number | null;
	remote_preference: RemotePreference;
	relocation_open: boolean;
	relocation_cities: string[];

	// Non-Negotiables: Compensation (REQ-001 §3.8.2)
	minimum_base_salary: number | null;
	salary_currency: string;

	// Non-Negotiables: Other Filters (REQ-001 §3.8.3)
	visa_sponsorship_required: boolean;
	industry_exclusions: string[];
	company_size_preference: CompanySizePreference;
	max_travel_percent: MaxTravelPercent;

	// Discovery Preferences (REQ-001 §3.10)
	minimum_fit_threshold: number;
	auto_draft_threshold: number;
	polling_frequency: PollingFrequency;

	// Onboarding state
	onboarding_complete: boolean;
	onboarding_step: string | null;

	// Timestamps
	created_at: string;
	updated_at: string;
}
