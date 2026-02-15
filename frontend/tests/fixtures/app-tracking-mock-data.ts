/**
 * Mock data factories for application tracking E2E tests.
 *
 * Returns API response envelopes (ApiResponse / ApiListResponse) with
 * realistic data shapes matching application.ts and api.ts.
 */

import type { ApiListResponse, ApiResponse, PaginationMeta } from "@/types/api";
import type {
	Application,
	InterviewStage,
	JobSnapshot,
	OfferDetails,
	RejectionDetails,
	TimelineEvent,
	TimelineEventType,
} from "@/types/application";
import type { Persona } from "@/types/persona";

// ---------------------------------------------------------------------------
// Consistent IDs
// ---------------------------------------------------------------------------

import { PERSONA_ID } from "./onboarding-mock-data";

export { PERSONA_ID };

export const APP_IDS = [
	"track-app-001",
	"track-app-002",
	"track-app-003",
	"track-app-004",
	"track-app-005",
	"track-app-006",
] as const;

export const TIMELINE_EVENT_IDS = [
	"te-001",
	"te-002",
	"te-003",
	"te-004",
] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NOW = "2026-02-15T12:00:00Z";

function listMeta(total: number): PaginationMeta {
	return { total, page: 1, per_page: 100, total_pages: 1 };
}

// ---------------------------------------------------------------------------
// Job snapshot fixtures (one per application, distinct companies)
// ---------------------------------------------------------------------------

const SNAPSHOTS: Record<string, JobSnapshot> = {
	[APP_IDS[0]]: {
		title: "Frontend Engineer",
		company_name: "AlphaTech",
		company_url: "https://alphatech.example.com",
		description: "Build modern React applications for our SaaS platform.",
		requirements: "3+ years React, TypeScript required.",
		salary_min: 140000,
		salary_max: 180000,
		salary_currency: "USD",
		location: "San Francisco, CA",
		work_model: "Hybrid",
		source_url: "https://linkedin.example.com/jobs/a001",
		captured_at: "2026-02-01T10:00:00Z",
	},
	[APP_IDS[1]]: {
		title: "Full Stack Developer",
		company_name: "BetaWorks",
		company_url: "https://betaworks.example.com",
		description: "Full stack role with Python backend and React frontend.",
		requirements: "4+ years full stack experience.",
		salary_min: 150000,
		salary_max: 190000,
		salary_currency: "USD",
		location: "Remote",
		work_model: "Remote",
		source_url: "https://indeed.example.com/jobs/b002",
		captured_at: "2026-02-03T10:00:00Z",
	},
	[APP_IDS[2]]: {
		title: "Senior Platform Engineer",
		company_name: "GammaCorp",
		company_url: "https://gammacorp.example.com",
		description: "Lead platform engineering for cloud infrastructure.",
		requirements: "5+ years infrastructure and Kubernetes.",
		salary_min: 180000,
		salary_max: 220000,
		salary_currency: "USD",
		location: "Seattle, WA",
		work_model: "Hybrid",
		source_url: "https://glassdoor.example.com/jobs/c003",
		captured_at: "2026-02-05T10:00:00Z",
	},
	[APP_IDS[3]]: {
		title: "Staff Engineer",
		company_name: "DeltaSoft",
		company_url: "https://deltasoft.example.com",
		description: "Staff-level IC role driving architecture decisions.",
		requirements: "8+ years engineering, system design expertise.",
		salary_min: 200000,
		salary_max: 250000,
		salary_currency: "USD",
		location: "New York, NY",
		work_model: "Onsite",
		source_url: "https://linkedin.example.com/jobs/d004",
		captured_at: "2026-02-07T10:00:00Z",
	},
	[APP_IDS[4]]: {
		title: "Backend Engineer",
		company_name: "EpsilonIO",
		company_url: "https://epsilonio.example.com",
		description: "Build high-throughput data pipelines in Python.",
		requirements: "3+ years Python, distributed systems.",
		salary_min: 145000,
		salary_max: 185000,
		salary_currency: "USD",
		location: "Austin, TX",
		work_model: "Remote",
		source_url: "https://indeed.example.com/jobs/e005",
		captured_at: "2026-02-09T10:00:00Z",
	},
	[APP_IDS[5]]: {
		title: "DevOps Engineer",
		company_name: "ZetaCloud",
		company_url: "https://zetacloud.example.com",
		description: "Manage CI/CD pipelines and cloud infrastructure.",
		requirements: "3+ years DevOps, AWS or GCP.",
		salary_min: 135000,
		salary_max: 175000,
		salary_currency: "USD",
		location: "Portland, OR",
		work_model: "Hybrid",
		source_url: "https://glassdoor.example.com/jobs/f006",
		captured_at: "2026-02-11T10:00:00Z",
	},
};

// ---------------------------------------------------------------------------
// Offer & Rejection detail fixtures
// ---------------------------------------------------------------------------

const OFFER_DETAILS: OfferDetails = {
	base_salary: 185000,
	salary_currency: "USD",
	bonus_percent: 15,
	equity_value: 50000,
	equity_type: "RSU",
	equity_vesting_years: 4,
	start_date: "2026-04-01",
	response_deadline: "2026-03-01",
	other_benefits: "401k 6% match, unlimited PTO",
	notes: "Negotiated from 170k",
};

const REJECTION_DETAILS: RejectionDetails = {
	stage: "Onsite",
	reason: "Position filled internally",
	feedback: "Strong candidate but went with internal promotion",
	rejected_at: "2026-02-10T15:30:00Z",
};

// ---------------------------------------------------------------------------
// Application fixtures
// ---------------------------------------------------------------------------

const BASE_APP: Application = {
	id: APP_IDS[0],
	persona_id: PERSONA_ID,
	job_posting_id: "jp-track-001",
	job_variant_id: "jv-track-001",
	cover_letter_id: null,
	submitted_resume_pdf_id: null,
	submitted_cover_letter_pdf_id: null,
	job_snapshot: SNAPSHOTS[APP_IDS[0]],
	status: "Applied",
	current_interview_stage: null,
	offer_details: null,
	rejection_details: null,
	notes: null,
	is_pinned: false,
	applied_at: "2026-02-01T10:00:00Z",
	status_updated_at: "2026-02-01T10:00:00Z",
	created_at: "2026-02-01T10:00:00Z",
	updated_at: "2026-02-01T10:00:00Z",
	archived_at: null,
};

const MOCK_APPLICATIONS: Application[] = [
	// track-app-001: Applied, no extras
	BASE_APP,

	// track-app-002: Interviewing, pinned, has notes
	{
		...BASE_APP,
		id: APP_IDS[1],
		job_posting_id: "jp-track-002",
		job_variant_id: "jv-track-002",
		job_snapshot: SNAPSHOTS[APP_IDS[1]],
		status: "Interviewing",
		current_interview_stage: "Phone Screen",
		notes: "Went well",
		is_pinned: true,
		applied_at: "2026-02-03T10:00:00Z",
		status_updated_at: "2026-02-05T10:00:00Z",
		created_at: "2026-02-03T10:00:00Z",
		updated_at: "2026-02-05T10:00:00Z",
	},

	// track-app-003: Offer, full OfferDetails
	{
		...BASE_APP,
		id: APP_IDS[2],
		job_posting_id: "jp-track-003",
		job_variant_id: "jv-track-003",
		job_snapshot: SNAPSHOTS[APP_IDS[2]],
		status: "Offer",
		offer_details: OFFER_DETAILS,
		applied_at: "2026-02-05T10:00:00Z",
		status_updated_at: "2026-02-12T10:00:00Z",
		created_at: "2026-02-05T10:00:00Z",
		updated_at: "2026-02-12T10:00:00Z",
	},

	// track-app-004: Accepted, full OfferDetails
	{
		...BASE_APP,
		id: APP_IDS[3],
		job_posting_id: "jp-track-004",
		job_variant_id: "jv-track-004",
		job_snapshot: SNAPSHOTS[APP_IDS[3]],
		status: "Accepted",
		offer_details: OFFER_DETAILS,
		applied_at: "2026-02-07T10:00:00Z",
		status_updated_at: "2026-02-14T10:00:00Z",
		created_at: "2026-02-07T10:00:00Z",
		updated_at: "2026-02-14T10:00:00Z",
	},

	// track-app-005: Rejected, full RejectionDetails
	{
		...BASE_APP,
		id: APP_IDS[4],
		job_posting_id: "jp-track-005",
		job_variant_id: "jv-track-005",
		job_snapshot: SNAPSHOTS[APP_IDS[4]],
		status: "Rejected",
		rejection_details: REJECTION_DETAILS,
		applied_at: "2026-02-09T10:00:00Z",
		status_updated_at: "2026-02-10T15:30:00Z",
		created_at: "2026-02-09T10:00:00Z",
		updated_at: "2026-02-10T15:30:00Z",
	},

	// track-app-006: Withdrawn, archived
	{
		...BASE_APP,
		id: APP_IDS[5],
		job_posting_id: "jp-track-006",
		job_variant_id: "jv-track-006",
		job_snapshot: SNAPSHOTS[APP_IDS[5]],
		status: "Withdrawn",
		applied_at: "2026-02-11T10:00:00Z",
		status_updated_at: "2026-02-13T10:00:00Z",
		created_at: "2026-02-11T10:00:00Z",
		updated_at: "2026-02-13T10:00:00Z",
		archived_at: "2026-02-13T12:00:00Z",
	},
];

// ---------------------------------------------------------------------------
// Timeline event fixtures (4 events for track-app-002)
// ---------------------------------------------------------------------------

const APP_002_TIMELINE_EVENTS: TimelineEvent[] = [
	{
		id: TIMELINE_EVENT_IDS[0],
		application_id: APP_IDS[1],
		event_type: "applied",
		event_date: "2026-02-01T10:00:00Z",
		description: null,
		interview_stage: null,
		created_at: "2026-02-01T10:00:00Z",
	},
	{
		id: TIMELINE_EVENT_IDS[1],
		application_id: APP_IDS[1],
		event_type: "status_changed",
		event_date: "2026-02-05T10:00:00Z",
		description: "Status changed to Interviewing",
		interview_stage: null,
		created_at: "2026-02-05T10:00:00Z",
	},
	{
		id: TIMELINE_EVENT_IDS[2],
		application_id: APP_IDS[1],
		event_type: "interview_scheduled",
		event_date: "2026-02-07T14:00:00Z",
		description: "Phone screen with hiring manager",
		interview_stage: "Phone Screen",
		created_at: "2026-02-07T10:00:00Z",
	},
	{
		id: TIMELINE_EVENT_IDS[3],
		application_id: APP_IDS[1],
		event_type: "follow_up_sent",
		event_date: "2026-02-10T09:00:00Z",
		description: "Thank you email sent",
		interview_stage: null,
		created_at: "2026-02-10T09:00:00Z",
	},
];

/** Default single "applied" event for apps other than track-app-002. */
function defaultAppliedEvent(appId: string): TimelineEvent {
	const app = MOCK_APPLICATIONS.find((a) => a.id === appId);
	return {
		id: `te-default-${appId}`,
		application_id: appId,
		event_type: "applied",
		event_date: app?.applied_at ?? NOW,
		description: null,
		interview_stage: null,
		created_at: app?.applied_at ?? NOW,
	};
}

// ---------------------------------------------------------------------------
// Persona factory (onboarded — re-export from onboarding fixtures)
// ---------------------------------------------------------------------------

const ONBOARDED_PERSONA: Persona = {
	id: PERSONA_ID,
	user_id: "00000000-0000-4000-a000-000000000099",
	full_name: "Jane Doe",
	email: "jane@example.com",
	phone: "+1 555-123-4567",
	home_city: "San Francisco",
	home_state: "CA",
	home_country: "USA",
	linkedin_url: "https://linkedin.example.com/in/janedoe",
	portfolio_url: null,
	professional_summary: "Experienced software engineer",
	years_experience: 8,
	current_role: "Senior Engineer",
	current_company: "Acme Corp",
	target_roles: ["Staff Engineer", "Engineering Manager"],
	target_skills: ["Kubernetes", "People Management"],
	stretch_appetite: "Medium",
	commutable_cities: ["San Francisco", "Oakland"],
	max_commute_minutes: 45,
	remote_preference: "Hybrid OK",
	relocation_open: false,
	relocation_cities: [],
	minimum_base_salary: 180000,
	salary_currency: "USD",
	visa_sponsorship_required: false,
	industry_exclusions: [],
	company_size_preference: "No Preference",
	max_travel_percent: "<25%",
	minimum_fit_threshold: 60,
	auto_draft_threshold: 80,
	polling_frequency: "Daily",
	onboarding_complete: true,
	onboarding_step: "base-resume",
	created_at: NOW,
	updated_at: NOW,
};

// ---------------------------------------------------------------------------
// Factory functions
// ---------------------------------------------------------------------------

/** Returns all 6 mock applications. */
export function allApplicationsList(): ApiListResponse<Application> {
	return { data: [...MOCK_APPLICATIONS], meta: listMeta(6) };
}

/** Returns a single application by ID (falls back to track-app-001). */
export function applicationDetail(id?: string): ApiResponse<Application> {
	const appId = id ?? APP_IDS[0];
	const app = MOCK_APPLICATIONS.find((a) => a.id === appId);
	return { data: app ?? MOCK_APPLICATIONS[0] };
}

/** Returns timeline events for a given application. */
export function timelineEventsList(
	appId: string,
): ApiListResponse<TimelineEvent> {
	if (appId === APP_IDS[1]) {
		return {
			data: [...APP_002_TIMELINE_EVENTS],
			meta: listMeta(4),
		};
	}
	// Other apps get a single "applied" event
	const event = defaultAppliedEvent(appId);
	return { data: [event], meta: listMeta(1) };
}

/** Returns an empty timeline events list. */
export function emptyTimelineEventsList(): ApiListResponse<TimelineEvent> {
	return { data: [], meta: listMeta(0) };
}

/** Returns a newly created timeline event response. */
export function postTimelineEventResponse(
	appId: string,
	eventType: TimelineEventType,
	description?: string,
	interviewStage?: InterviewStage,
): ApiResponse<TimelineEvent> {
	return {
		data: {
			id: `te-new-${Date.now()}`,
			application_id: appId,
			event_type: eventType,
			event_date: NOW,
			description: description ?? null,
			interview_stage: interviewStage ?? null,
			created_at: NOW,
		},
	};
}

/** Returns an onboarded persona list (onboarding_complete=true). */
export function onboardedPersonaList(): ApiListResponse<Persona> {
	return { data: [{ ...ONBOARDED_PERSONA }], meta: listMeta(1) };
}

// ---------------------------------------------------------------------------
// Exported constants for mock controller
// ---------------------------------------------------------------------------

export { MOCK_APPLICATIONS, APP_002_TIMELINE_EVENTS, SNAPSHOTS };
