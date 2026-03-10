import { describe, expect, it } from "vitest";

import type {
	Application,
	ApplicationStatus,
	CoverLetter,
	CoverLetterStatus,
	CoverLetterValidation,
	InterviewStage,
	JobSnapshot,
	OfferDetails,
	RejectionDetails,
	SubmittedCoverLetterPDF,
	TimelineEvent,
	TimelineEventType,
	ValidationIssue,
	ValidationSeverity,
} from "./application";
import {
	APPLICATION_STATUSES,
	COVER_LETTER_STATUSES,
	INTERVIEW_STAGES,
	TIMELINE_EVENT_TYPES,
	VALIDATION_SEVERITIES,
} from "./application";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const IDS = {
	application: "aa0e8400-e29b-41d4-a716-667755440000",
	persona: "bb0e8400-e29b-41d4-a716-667755440000",
	jobPosting: "cc0e8400-e29b-41d4-a716-667755440000",
	jobVariant: "dd0e8400-e29b-41d4-a716-667755440000",
	coverLetter: "ee0e8400-e29b-41d4-a716-667755440000",
	submittedResumePdf: "ff0e8400-e29b-41d4-a716-667755440000",
	submittedCoverLetterPdf: "110e8400-e29b-41d4-a716-667755440000",
	timelineEvent: "220e8400-e29b-41d4-a716-667755440000",
	story1: "330e8400-e29b-41d4-a716-667755440000",
	story2: "440e8400-e29b-41d4-a716-667755440000",
} as const;

const TIMESTAMPS = {
	created: "2025-01-15T10:00:00Z",
	updated: "2025-02-01T14:30:00Z",
	applied: "2025-01-20T09:00:00Z",
	statusUpdated: "2025-02-03T11:00:00Z",
	approved: "2025-02-05T16:00:00Z",
	archived: "2025-02-06T00:00:00Z",
	generated: "2025-02-04T12:00:00Z",
	eventDate: "2025-01-25T14:00:00Z",
	captured: "2025-01-20T09:00:00Z",
	rejected: "2025-02-10T10:00:00Z",
	startDate: "2025-03-15",
	deadline: "2025-02-20",
} as const;

const VALIDATION_RULES = {
	lengthMin: "length_min",
	lengthMax: "length_max",
	blacklist: "blacklist_violation",
	companySpecificity: "company_specificity",
	metricAccuracy: "metric_accuracy",
	fabrication: "potential_fabrication",
} as const;

// ---------------------------------------------------------------------------
// Factory functions
// ---------------------------------------------------------------------------

function makeJobSnapshot(overrides: Partial<JobSnapshot> = {}): JobSnapshot {
	return {
		title: "Senior Software Engineer",
		company_name: "Acme Corp",
		company_url: "https://acme.example.com",
		description: "Build scalable distributed systems.",
		requirements: "5+ years experience, distributed systems",
		salary_min: 150000,
		salary_max: 200000,
		salary_currency: "USD",
		location: "San Francisco, CA",
		work_model: "Hybrid",
		source_url: "https://jobs.example.com/12345",
		captured_at: TIMESTAMPS.captured,
		...overrides,
	};
}

function makeOfferDetails(overrides: Partial<OfferDetails> = {}): OfferDetails {
	return {
		base_salary: 175000,
		salary_currency: "USD",
		bonus_percent: 15,
		equity_value: 50000,
		equity_type: "RSU",
		equity_vesting_years: 4,
		start_date: TIMESTAMPS.startDate,
		response_deadline: TIMESTAMPS.deadline,
		other_benefits: "Health, dental, 401k match",
		notes: "Relocation package included",
		...overrides,
	};
}

function makeRejectionDetails(
	overrides: Partial<RejectionDetails> = {},
): RejectionDetails {
	return {
		stage: "Onsite",
		reason: "Culture fit concerns",
		feedback: "Looking for someone more senior",
		rejected_at: TIMESTAMPS.rejected,
		...overrides,
	};
}

function makeApplication(overrides: Partial<Application> = {}): Application {
	return {
		id: IDS.application,
		persona_id: IDS.persona,
		job_posting_id: IDS.jobPosting,
		job_variant_id: IDS.jobVariant,
		cover_letter_id: IDS.coverLetter,
		submitted_resume_pdf_id: IDS.submittedResumePdf,
		submitted_cover_letter_pdf_id: IDS.submittedCoverLetterPdf,
		job_snapshot: makeJobSnapshot(),
		status: "Applied",
		current_interview_stage: null,
		offer_details: null,
		rejection_details: null,
		notes: null,
		is_pinned: false,
		applied_at: TIMESTAMPS.applied,
		status_updated_at: TIMESTAMPS.statusUpdated,
		created_at: TIMESTAMPS.created,
		updated_at: TIMESTAMPS.updated,
		archived_at: null,
		...overrides,
	};
}

function makeTimelineEvent(
	overrides: Partial<TimelineEvent> = {},
): TimelineEvent {
	return {
		id: IDS.timelineEvent,
		application_id: IDS.application,
		event_type: "applied",
		event_date: TIMESTAMPS.eventDate,
		description: "Application submitted",
		interview_stage: null,
		created_at: TIMESTAMPS.created,
		...overrides,
	};
}

function makeCoverLetter(overrides: Partial<CoverLetter> = {}): CoverLetter {
	return {
		id: IDS.coverLetter,
		persona_id: IDS.persona,
		application_id: IDS.application,
		job_posting_id: IDS.jobPosting,
		achievement_stories_used: [IDS.story1, IDS.story2],
		draft_text: "Dear Hiring Manager, I am excited to apply...",
		final_text: null,
		status: "Draft",
		agent_reasoning: "Selected stories for leadership and technical alignment.",
		validation_result: null,
		approved_at: null,
		created_at: TIMESTAMPS.created,
		updated_at: TIMESTAMPS.updated,
		archived_at: null,
		...overrides,
	};
}

function makeSubmittedCoverLetterPDF(
	overrides: Partial<SubmittedCoverLetterPDF> = {},
): SubmittedCoverLetterPDF {
	return {
		id: IDS.submittedCoverLetterPdf,
		cover_letter_id: IDS.coverLetter,
		application_id: IDS.application,
		file_name: "cover_letter_acme_corp.pdf",
		generated_at: TIMESTAMPS.generated,
		...overrides,
	};
}

// ---------------------------------------------------------------------------
// Union type tests
// ---------------------------------------------------------------------------

describe("ApplicationStatus", () => {
	it("accepts all valid statuses", () => {
		const statuses: ApplicationStatus[] = [
			"Applied",
			"Interviewing",
			"Offer",
			"Accepted",
			"Rejected",
			"Withdrawn",
		];
		expect(statuses).toHaveLength(6);
	});
});

describe("InterviewStage", () => {
	it("accepts all valid stages", () => {
		const stages: InterviewStage[] = ["Phone Screen", "Onsite", "Final Round"];
		expect(stages).toHaveLength(3);
	});
});

describe("TimelineEventType", () => {
	it("accepts all valid event types", () => {
		const types: TimelineEventType[] = [
			"applied",
			"status_changed",
			"note_added",
			"interview_scheduled",
			"interview_completed",
			"offer_received",
			"offer_accepted",
			"rejected",
			"withdrawn",
			"follow_up_sent",
			"response_received",
			"custom",
		];
		expect(types).toHaveLength(12);
	});
});

describe("CoverLetterStatus", () => {
	it("accepts all valid statuses", () => {
		const statuses: CoverLetterStatus[] = ["Draft", "Approved", "Archived"];
		expect(statuses).toHaveLength(3);
	});
});

describe("ValidationSeverity", () => {
	it("accepts all valid severities", () => {
		const severities: ValidationSeverity[] = ["error", "warning"];
		expect(severities).toHaveLength(2);
	});
});

// ---------------------------------------------------------------------------
// Value array tests
// ---------------------------------------------------------------------------

describe("APPLICATION_STATUSES", () => {
	it("contains all statuses in correct order", () => {
		expect(APPLICATION_STATUSES).toEqual([
			"Applied",
			"Interviewing",
			"Offer",
			"Accepted",
			"Rejected",
			"Withdrawn",
		]);
	});
});

describe("INTERVIEW_STAGES", () => {
	it("contains all stages in correct order", () => {
		expect(INTERVIEW_STAGES).toEqual(["Phone Screen", "Onsite", "Final Round"]);
	});
});

describe("TIMELINE_EVENT_TYPES", () => {
	it("contains all event types in correct order", () => {
		expect(TIMELINE_EVENT_TYPES).toEqual([
			"applied",
			"status_changed",
			"note_added",
			"interview_scheduled",
			"interview_completed",
			"offer_received",
			"offer_accepted",
			"rejected",
			"withdrawn",
			"follow_up_sent",
			"response_received",
			"custom",
		]);
	});
});

describe("COVER_LETTER_STATUSES", () => {
	it("contains all statuses in correct order", () => {
		expect(COVER_LETTER_STATUSES).toEqual(["Draft", "Approved", "Archived"]);
	});
});

describe("VALIDATION_SEVERITIES", () => {
	it("contains all severities in correct order", () => {
		expect(VALIDATION_SEVERITIES).toEqual(["error", "warning"]);
	});
});

// ---------------------------------------------------------------------------
// Sub-entity interface tests
// ---------------------------------------------------------------------------

describe("JobSnapshot", () => {
	it("represents a frozen job posting copy with all fields", () => {
		const snapshot = makeJobSnapshot();
		expect(snapshot.title).toBe("Senior Software Engineer");
		expect(snapshot.company_name).toBe("Acme Corp");
		expect(snapshot.captured_at).toBe(TIMESTAMPS.captured);
	});

	it("allows nullable fields", () => {
		const snapshot = makeJobSnapshot({
			company_url: null,
			requirements: null,
			salary_min: null,
			salary_max: null,
			salary_currency: null,
			location: null,
			work_model: null,
			source_url: null,
		});
		expect(snapshot.company_url).toBeNull();
		expect(snapshot.salary_min).toBeNull();
		expect(snapshot.location).toBeNull();
	});
});

describe("OfferDetails", () => {
	it("represents a complete offer with all fields", () => {
		const offer = makeOfferDetails();
		expect(offer.base_salary).toBe(175000);
		expect(offer.equity_type).toBe("RSU");
		expect(offer.response_deadline).toBe(TIMESTAMPS.deadline);
	});

	it("allows all fields to be undefined (all optional)", () => {
		const offer: OfferDetails = {};
		expect(offer.base_salary).toBeUndefined();
		expect(offer.equity_type).toBeUndefined();
	});
});

describe("RejectionDetails", () => {
	it("represents a rejection with all fields", () => {
		const rejection = makeRejectionDetails();
		expect(rejection.stage).toBe("Onsite");
		expect(rejection.reason).toBe("Culture fit concerns");
		expect(rejection.rejected_at).toBe(TIMESTAMPS.rejected);
	});

	it("allows all fields to be undefined (all optional)", () => {
		const rejection: RejectionDetails = {};
		expect(rejection.stage).toBeUndefined();
		expect(rejection.feedback).toBeUndefined();
	});
});

describe("ValidationIssue", () => {
	it("represents a cover letter validation issue", () => {
		const issue: ValidationIssue = {
			severity: "error",
			rule: VALIDATION_RULES.lengthMin,
			message: "Too short: 180 words (minimum 250)",
		};
		expect(issue.severity).toBe("error");
		expect(issue.rule).toBe(VALIDATION_RULES.lengthMin);
	});

	it("supports warning severity", () => {
		const issue: ValidationIssue = {
			severity: "warning",
			rule: VALIDATION_RULES.companySpecificity,
			message: "Company name not in opening paragraph",
		};
		expect(issue.severity).toBe("warning");
	});
});

describe("CoverLetterValidation", () => {
	it("represents a passing validation result", () => {
		const result: CoverLetterValidation = {
			passed: true,
			issues: [],
			word_count: 300,
		};
		expect(result.passed).toBe(true);
		expect(result.issues).toHaveLength(0);
		expect(result.word_count).toBe(300);
	});

	it("represents a failing validation with mixed severities", () => {
		const result: CoverLetterValidation = {
			passed: false,
			issues: [
				{
					severity: "error",
					rule: VALIDATION_RULES.blacklist,
					message: "Contains avoided phrase: 'synergy'",
				},
				{
					severity: "warning",
					rule: VALIDATION_RULES.lengthMax,
					message: "Long: 380 words (target 250-350)",
				},
			],
			word_count: 380,
		};
		expect(result.passed).toBe(false);
		expect(result.issues).toHaveLength(2);
	});
});

// ---------------------------------------------------------------------------
// Main entity interface tests
// ---------------------------------------------------------------------------

describe("Application", () => {
	it("represents a new application with minimal state", () => {
		const app = makeApplication();
		expect(app.id).toBe(IDS.application);
		expect(app.persona_id).toBe(IDS.persona);
		expect(app.job_posting_id).toBe(IDS.jobPosting);
		expect(app.job_variant_id).toBe(IDS.jobVariant);
		expect(app.status).toBe("Applied");
		expect(app.current_interview_stage).toBeNull();
		expect(app.offer_details).toBeNull();
		expect(app.rejection_details).toBeNull();
		expect(app.is_pinned).toBe(false);
		expect(app.archived_at).toBeNull();
	});

	it("represents an interviewing application with stage", () => {
		const app = makeApplication({
			status: "Interviewing",
			current_interview_stage: "Phone Screen",
		});
		expect(app.status).toBe("Interviewing");
		expect(app.current_interview_stage).toBe("Phone Screen");
	});

	it("represents an offer with details", () => {
		const app = makeApplication({
			status: "Offer",
			offer_details: makeOfferDetails(),
		});
		expect(app.status).toBe("Offer");
		expect(app.offer_details).not.toBeNull();
		expect(app.offer_details!.base_salary).toBe(175000);
	});

	it("represents a rejected application", () => {
		const app = makeApplication({
			status: "Rejected",
			rejection_details: makeRejectionDetails(),
		});
		expect(app.status).toBe("Rejected");
		expect(app.rejection_details).not.toBeNull();
		expect(app.rejection_details!.stage).toBe("Onsite");
	});

	it("supports optional PDF links as null", () => {
		const app = makeApplication({
			cover_letter_id: null,
			submitted_resume_pdf_id: null,
			submitted_cover_letter_pdf_id: null,
		});
		expect(app.cover_letter_id).toBeNull();
		expect(app.submitted_resume_pdf_id).toBeNull();
		expect(app.submitted_cover_letter_pdf_id).toBeNull();
	});

	it("supports notes and pinning", () => {
		const app = makeApplication({
			notes: "Great culture fit, follow up next week",
			is_pinned: true,
		});
		expect(app.notes).toBe("Great culture fit, follow up next week");
		expect(app.is_pinned).toBe(true);
	});

	it("supports archived state", () => {
		const app = makeApplication({
			archived_at: TIMESTAMPS.archived,
		});
		expect(app.archived_at).toBe(TIMESTAMPS.archived);
	});

	it("embeds job snapshot", () => {
		const app = makeApplication();
		expect(app.job_snapshot.title).toBe("Senior Software Engineer");
		expect(app.job_snapshot.company_name).toBe("Acme Corp");
		expect(app.job_snapshot.captured_at).toBe(TIMESTAMPS.captured);
	});
});

describe("TimelineEvent", () => {
	it("represents a basic applied event", () => {
		const event = makeTimelineEvent();
		expect(event.id).toBe(IDS.timelineEvent);
		expect(event.application_id).toBe(IDS.application);
		expect(event.event_type).toBe("applied");
		expect(event.description).toBe("Application submitted");
		expect(event.interview_stage).toBeNull();
	});

	it("represents an interview event with stage", () => {
		const event = makeTimelineEvent({
			event_type: "interview_scheduled",
			description: "Phone screen with hiring manager",
			interview_stage: "Phone Screen",
		});
		expect(event.event_type).toBe("interview_scheduled");
		expect(event.interview_stage).toBe("Phone Screen");
	});

	it("supports null description", () => {
		const event = makeTimelineEvent({ description: null });
		expect(event.description).toBeNull();
	});

	it("represents a custom event", () => {
		const event = makeTimelineEvent({
			event_type: "custom",
			description: "Received positive LinkedIn message from team member",
		});
		expect(event.event_type).toBe("custom");
	});

	it("has no updated_at field (immutable events)", () => {
		const event = makeTimelineEvent();
		expect("updated_at" in event).toBe(false);
	});
});

describe("CoverLetter", () => {
	it("represents a draft cover letter", () => {
		const letter = makeCoverLetter();
		expect(letter.id).toBe(IDS.coverLetter);
		expect(letter.persona_id).toBe(IDS.persona);
		expect(letter.job_posting_id).toBe(IDS.jobPosting);
		expect(letter.status).toBe("Draft");
		expect(letter.draft_text).toContain("Dear Hiring Manager");
		expect(letter.final_text).toBeNull();
		expect(letter.approved_at).toBeNull();
	});

	it("represents an approved cover letter with final text", () => {
		const letter = makeCoverLetter({
			status: "Approved",
			final_text: "Dear Hiring Manager, final version...",
			approved_at: TIMESTAMPS.approved,
		});
		expect(letter.status).toBe("Approved");
		expect(letter.final_text).toBe("Dear Hiring Manager, final version...");
		expect(letter.approved_at).toBe(TIMESTAMPS.approved);
	});

	it("tracks achievement stories used", () => {
		const letter = makeCoverLetter();
		expect(letter.achievement_stories_used).toEqual([IDS.story1, IDS.story2]);
	});

	it("supports null application_id before linking", () => {
		const letter = makeCoverLetter({ application_id: null });
		expect(letter.application_id).toBeNull();
	});

	it("supports null agent_reasoning", () => {
		const letter = makeCoverLetter({ agent_reasoning: null });
		expect(letter.agent_reasoning).toBeNull();
	});

	it("supports archived state", () => {
		const letter = makeCoverLetter({
			status: "Archived",
			archived_at: TIMESTAMPS.archived,
		});
		expect(letter.status).toBe("Archived");
		expect(letter.archived_at).toBe(TIMESTAMPS.archived);
	});
});

describe("SubmittedCoverLetterPDF", () => {
	it("represents a submitted cover letter PDF", () => {
		const pdf = makeSubmittedCoverLetterPDF();
		expect(pdf.id).toBe(IDS.submittedCoverLetterPdf);
		expect(pdf.cover_letter_id).toBe(IDS.coverLetter);
		expect(pdf.file_name).toBe("cover_letter_acme_corp.pdf");
		expect(pdf.generated_at).toBe(TIMESTAMPS.generated);
	});

	it("supports null application_id for orphan PDFs", () => {
		const pdf = makeSubmittedCoverLetterPDF({ application_id: null });
		expect(pdf.application_id).toBeNull();
	});
});
