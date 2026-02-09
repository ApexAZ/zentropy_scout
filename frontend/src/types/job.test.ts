import { describe, expect, it } from "vitest";

import type {
	AlsoFoundOn,
	CrossSourceEntry,
	ExtractedSkill,
	FailedNonNegotiable,
	FitScoreComponentKey,
	FitScoreResult,
	FitScoreTier,
	GhostScoreTier,
	GhostSignals,
	JobPosting,
	JobPostingStatus,
	ScoreDetails,
	ScoreExplanation,
	SeniorityLevel,
	StretchScoreComponentKey,
	StretchScoreResult,
	StretchScoreTier,
} from "./job";
import {
	FIT_SCORE_COMPONENT_KEYS,
	FIT_SCORE_TIERS,
	GHOST_SCORE_TIERS,
	JOB_POSTING_STATUSES,
	SENIORITY_LEVELS,
	STRETCH_SCORE_COMPONENT_KEYS,
	STRETCH_SCORE_TIERS,
} from "./job";

// ---------------------------------------------------------------------------
// Shared test fixtures — avoids S1192 (duplicated string literals)
// ---------------------------------------------------------------------------

const IDS = {
	jobPosting: "aa0e8400-e29b-41d4-a716-446655440000",
	persona: "bb0e8400-e29b-41d4-a716-446655440000",
	source: "cc0e8400-e29b-41d4-a716-446655440000",
	crossSource: "dd0e8400-e29b-41d4-a716-446655440000",
	extractedSkill: "ee0e8400-e29b-41d4-a716-446655440000",
	extractedSkill2: "ee0e8400-e29b-41d4-a716-446655440001",
	previousPosting1: "ff0e8400-e29b-41d4-a716-446655440001",
	previousPosting2: "ff0e8400-e29b-41d4-a716-446655440002",
} as const;

const TIMESTAMPS = {
	created: "2025-01-15T10:00:00Z",
	updated: "2025-02-01T14:30:00Z",
	firstSeen: "2025-01-10",
	posted: "2025-01-08",
	deadline: "2025-03-01",
	lastVerified: "2025-02-05T08:00:00Z",
	dismissed: "2025-02-03T16:00:00Z",
	expired: "2025-02-06T00:00:00Z",
	ghostCalculated: "2025-02-01T12:00:00Z",
	crossSourceFound: "2025-01-20T09:00:00Z",
} as const;

const HASHES = {
	description:
		"a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
	description2:
		"b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
} as const;

const FILTER_NAMES = {
	minimumBaseSalary: "minimum_base_salary",
	remotePreference: "remote_preference",
} as const;

const SCORE_TEXTS = {
	fitSummary: "Strong technical fit.",
} as const;

/** Reusable fit score result matching backend _SAMPLE_FIT. */
const SAMPLE_FIT: FitScoreResult = {
	total: 85,
	components: {
		hard_skills: 90.0,
		soft_skills: 75.0,
		experience_level: 88.0,
		role_title: 72.0,
		location_logistics: 95.0,
	},
	weights: {
		hard_skills: 0.4,
		soft_skills: 0.15,
		experience_level: 0.25,
		role_title: 0.1,
		location_logistics: 0.1,
	},
};

/** Reusable stretch score result matching backend _SAMPLE_STRETCH. */
const SAMPLE_STRETCH: StretchScoreResult = {
	total: 72,
	components: {
		target_role: 80.0,
		target_skills: 60.0,
		growth_trajectory: 70.0,
	},
	weights: {
		target_role: 0.5,
		target_skills: 0.4,
		growth_trajectory: 0.1,
	},
};

/** Reusable explanation fixture. */
const SAMPLE_EXPLANATION: ScoreExplanation = {
	summary: SCORE_TEXTS.fitSummary,
	strengths: ["Python", "FastAPI"],
	gaps: ["Kubernetes"],
	stretch_opportunities: ["ML pipeline"],
	warnings: [],
};

/** Factory for JobPosting with sensible defaults. Override only what differs. */
function makeJobPosting(overrides: Partial<JobPosting> = {}): JobPosting {
	return {
		id: IDS.jobPosting,
		persona_id: IDS.persona,
		external_id: null,
		source_id: IDS.source,
		also_found_on: { sources: [] },
		job_title: "Senior Python Developer",
		company_name: "Acme Corp",
		company_url: null,
		source_url: null,
		apply_url: null,
		location: null,
		work_model: null,
		seniority_level: null,
		salary_min: null,
		salary_max: null,
		salary_currency: null,
		description: "We are looking for a senior Python developer...",
		culture_text: null,
		requirements: null,
		years_experience_min: null,
		years_experience_max: null,
		posted_date: null,
		application_deadline: null,
		first_seen_date: TIMESTAMPS.firstSeen,
		status: "Discovered",
		is_favorite: false,
		fit_score: null,
		stretch_score: null,
		score_details: null,
		failed_non_negotiables: null,
		ghost_score: 0,
		ghost_signals: null,
		description_hash: HASHES.description,
		repost_count: 0,
		previous_posting_ids: null,
		last_verified_at: null,
		dismissed_at: null,
		expired_at: null,
		created_at: TIMESTAMPS.created,
		updated_at: TIMESTAMPS.updated,
		...overrides,
	};
}

// ---------------------------------------------------------------------------
// Enum value arrays
// ---------------------------------------------------------------------------

describe("Job Enum Value Arrays", () => {
	describe("SENIORITY_LEVELS", () => {
		it("contains all seniority levels in order", () => {
			expect(SENIORITY_LEVELS).toEqual([
				"Entry",
				"Mid",
				"Senior",
				"Lead",
				"Executive",
			]);
		});

		it("satisfies the SeniorityLevel type", () => {
			const level: SeniorityLevel = SENIORITY_LEVELS[0];
			expect(level).toBe("Entry");
		});
	});

	describe("JOB_POSTING_STATUSES", () => {
		it("contains all statuses in order", () => {
			expect(JOB_POSTING_STATUSES).toEqual([
				"Discovered",
				"Dismissed",
				"Applied",
				"Expired",
			]);
		});

		it("satisfies the JobPostingStatus type", () => {
			const status: JobPostingStatus = JOB_POSTING_STATUSES[0];
			expect(status).toBe("Discovered");
		});
	});

	describe("FIT_SCORE_TIERS", () => {
		it("contains all fit score tiers in descending order", () => {
			expect(FIT_SCORE_TIERS).toEqual(["High", "Medium", "Low", "Poor"]);
		});

		it("satisfies the FitScoreTier type", () => {
			const tier: FitScoreTier = FIT_SCORE_TIERS[0];
			expect(tier).toBe("High");
		});
	});

	describe("STRETCH_SCORE_TIERS", () => {
		it("contains all stretch score tiers in descending order", () => {
			expect(STRETCH_SCORE_TIERS).toEqual([
				"High Growth",
				"Moderate Growth",
				"Lateral",
				"Low Growth",
			]);
		});

		it("satisfies the StretchScoreTier type", () => {
			const tier: StretchScoreTier = STRETCH_SCORE_TIERS[0];
			expect(tier).toBe("High Growth");
		});
	});

	describe("GHOST_SCORE_TIERS", () => {
		it("contains all ghost score tiers in ascending risk order", () => {
			expect(GHOST_SCORE_TIERS).toEqual([
				"Fresh",
				"Moderate",
				"Elevated",
				"High Risk",
			]);
		});

		it("satisfies the GhostScoreTier type", () => {
			const tier: GhostScoreTier = GHOST_SCORE_TIERS[0];
			expect(tier).toBe("Fresh");
		});
	});

	describe("FIT_SCORE_COMPONENT_KEYS", () => {
		it("contains all 5 fit score component keys", () => {
			expect(FIT_SCORE_COMPONENT_KEYS).toEqual([
				"hard_skills",
				"soft_skills",
				"experience_level",
				"role_title",
				"location_logistics",
			]);
		});

		it("satisfies the FitScoreComponentKey type", () => {
			const key: FitScoreComponentKey = FIT_SCORE_COMPONENT_KEYS[0];
			expect(key).toBe("hard_skills");
		});
	});

	describe("STRETCH_SCORE_COMPONENT_KEYS", () => {
		it("contains all 3 stretch score component keys", () => {
			expect(STRETCH_SCORE_COMPONENT_KEYS).toEqual([
				"target_role",
				"target_skills",
				"growth_trajectory",
			]);
		});

		it("satisfies the StretchScoreComponentKey type", () => {
			const key: StretchScoreComponentKey = STRETCH_SCORE_COMPONENT_KEYS[0];
			expect(key).toBe("target_role");
		});
	});
});

// ---------------------------------------------------------------------------
// Sub-entity interfaces
// ---------------------------------------------------------------------------

describe("Job Sub-Entity Types", () => {
	describe("CrossSourceEntry", () => {
		it("represents a cross-source job listing reference", () => {
			const entry: CrossSourceEntry = {
				source_id: IDS.crossSource,
				external_id: "linkedin-job-12345",
				source_url: "https://linkedin.com/jobs/12345",
				found_at: TIMESTAMPS.crossSourceFound,
			};

			expect(entry.source_id).toBe(IDS.crossSource);
			expect(entry.external_id).toBe("linkedin-job-12345");
			expect(entry.source_url).toBe("https://linkedin.com/jobs/12345");
			expect(entry.found_at).toBe(TIMESTAMPS.crossSourceFound);
		});
	});

	describe("AlsoFoundOn", () => {
		it("wraps an array of cross-source entries", () => {
			const alsoFoundOn: AlsoFoundOn = {
				sources: [
					{
						source_id: IDS.crossSource,
						external_id: "indeed-456",
						source_url: "https://indeed.com/jobs/456",
						found_at: TIMESTAMPS.crossSourceFound,
					},
				],
			};

			expect(alsoFoundOn.sources).toHaveLength(1);
			expect(alsoFoundOn.sources[0].source_id).toBe(IDS.crossSource);
		});

		it("defaults to empty sources array", () => {
			const alsoFoundOn: AlsoFoundOn = { sources: [] };
			expect(alsoFoundOn.sources).toHaveLength(0);
		});
	});

	describe("FailedNonNegotiable", () => {
		it("represents a string-valued filter failure", () => {
			const failure: FailedNonNegotiable = {
				filter: FILTER_NAMES.remotePreference,
				job_value: "Onsite",
				persona_value: "Remote Only",
			};

			expect(failure.filter).toBe(FILTER_NAMES.remotePreference);
			expect(failure.job_value).toBe("Onsite");
			expect(failure.persona_value).toBe("Remote Only");
		});

		it("represents a numeric-valued filter failure", () => {
			const failure: FailedNonNegotiable = {
				filter: FILTER_NAMES.minimumBaseSalary,
				job_value: 60000,
				persona_value: 80000,
			};

			expect(failure.job_value).toBe(60000);
			expect(failure.persona_value).toBe(80000);
		});

		it("allows null values when data is missing", () => {
			const failure: FailedNonNegotiable = {
				filter: FILTER_NAMES.minimumBaseSalary,
				job_value: null,
				persona_value: 80000,
			};

			expect(failure.job_value).toBeNull();
		});
	});

	describe("ExtractedSkill", () => {
		it("represents a required hard skill", () => {
			const skill: ExtractedSkill = {
				id: IDS.extractedSkill,
				job_posting_id: IDS.jobPosting,
				skill_name: "Python",
				skill_type: "Hard",
				is_required: true,
				years_requested: 5,
			};

			expect(skill.skill_name).toBe("Python");
			expect(skill.skill_type).toBe("Hard");
			expect(skill.is_required).toBe(true);
			expect(skill.years_requested).toBe(5);
		});

		it("represents an optional soft skill with no years", () => {
			const skill: ExtractedSkill = {
				id: IDS.extractedSkill2,
				job_posting_id: IDS.jobPosting,
				skill_name: "Leadership",
				skill_type: "Soft",
				is_required: false,
				years_requested: null,
			};

			expect(skill.skill_type).toBe("Soft");
			expect(skill.is_required).toBe(false);
			expect(skill.years_requested).toBeNull();
		});
	});
});

// ---------------------------------------------------------------------------
// Scoring types
// ---------------------------------------------------------------------------

describe("Scoring Types", () => {
	describe("FitScoreResult", () => {
		it("contains total, components, and weights", () => {
			const result: FitScoreResult = { ...SAMPLE_FIT };

			expect(result.total).toBe(85);
			expect(Object.keys(result.components)).toHaveLength(5);
			expect(result.components.hard_skills).toBe(90.0);
			expect(result.weights.hard_skills).toBe(0.4);
		});
	});

	describe("StretchScoreResult", () => {
		it("contains total, components, and weights", () => {
			const result: StretchScoreResult = { ...SAMPLE_STRETCH };

			expect(result.total).toBe(72);
			expect(Object.keys(result.components)).toHaveLength(3);
			expect(result.components.target_role).toBe(80.0);
			expect(result.weights.target_role).toBe(0.5);
		});
	});

	describe("ScoreExplanation", () => {
		it("contains all explanation sections", () => {
			const explanation: ScoreExplanation = {
				summary: "Strong technical fit with minor experience gap.",
				strengths: ["5/6 required skills", "Role title match"],
				gaps: ["Kubernetes experience"],
				stretch_opportunities: ["ML pipeline exposure"],
				warnings: ["Salary not disclosed"],
			};

			expect(explanation.summary).toBe(
				"Strong technical fit with minor experience gap.",
			);
			expect(explanation.strengths).toHaveLength(2);
			expect(explanation.gaps).toHaveLength(1);
			expect(explanation.stretch_opportunities).toHaveLength(1);
			expect(explanation.warnings).toHaveLength(1);
		});

		it("allows empty arrays for optional sections", () => {
			const explanation: ScoreExplanation = {
				summary: "Perfect match.",
				strengths: ["All skills match"],
				gaps: [],
				stretch_opportunities: [],
				warnings: [],
			};

			expect(explanation.gaps).toHaveLength(0);
			expect(explanation.warnings).toHaveLength(0);
		});
	});

	describe("ScoreDetails", () => {
		it("combines fit, stretch, and explanation", () => {
			const details: ScoreDetails = {
				fit: SAMPLE_FIT,
				stretch: SAMPLE_STRETCH,
				explanation: SAMPLE_EXPLANATION,
			};

			expect(details.fit.total).toBe(85);
			expect(details.stretch.total).toBe(72);
			expect(details.explanation.summary).toBe(SCORE_TEXTS.fitSummary);
		});
	});

	describe("GhostSignals", () => {
		it("contains all ghost detection signal fields", () => {
			const signals: GhostSignals = {
				days_open: 45,
				days_open_score: 50,
				repost_count: 2,
				repost_score: 60,
				vagueness_score: 30,
				missing_fields: ["salary", "deadline"],
				missing_fields_score: 67,
				requirement_mismatch: false,
				requirement_mismatch_score: 0,
				calculated_at: TIMESTAMPS.ghostCalculated,
				ghost_score: 42,
			};

			expect(signals.days_open).toBe(45);
			expect(signals.days_open_score).toBe(50);
			expect(signals.repost_count).toBe(2);
			expect(signals.repost_score).toBe(60);
			expect(signals.vagueness_score).toBe(30);
			expect(signals.missing_fields).toEqual(["salary", "deadline"]);
			expect(signals.missing_fields_score).toBe(67);
			expect(signals.requirement_mismatch).toBe(false);
			expect(signals.requirement_mismatch_score).toBe(0);
			expect(signals.calculated_at).toBe(TIMESTAMPS.ghostCalculated);
			expect(signals.ghost_score).toBe(42);
		});

		it("supports empty missing fields", () => {
			const signals: GhostSignals = {
				days_open: 5,
				days_open_score: 0,
				repost_count: 0,
				repost_score: 0,
				vagueness_score: 10,
				missing_fields: [],
				missing_fields_score: 0,
				requirement_mismatch: false,
				requirement_mismatch_score: 0,
				calculated_at: TIMESTAMPS.ghostCalculated,
				ghost_score: 3,
			};

			expect(signals.missing_fields).toHaveLength(0);
			expect(signals.ghost_score).toBe(3);
		});
	});
});

// ---------------------------------------------------------------------------
// Main JobPosting interface
// ---------------------------------------------------------------------------

describe("JobPosting", () => {
	it("represents a minimal job posting with required fields only", () => {
		const job = makeJobPosting();

		expect(job.id).toBe(IDS.jobPosting);
		expect(job.status).toBe("Discovered");
		expect(job.is_favorite).toBe(false);
		expect(job.ghost_score).toBe(0);
		expect(job.score_details).toBeNull();
		expect(job.description_hash).toBe(HASHES.description);
	});

	it("represents a fully populated job posting", () => {
		const job = makeJobPosting({
			external_id: "linkedin-98765",
			also_found_on: {
				sources: [
					{
						source_id: IDS.crossSource,
						external_id: "indeed-456",
						source_url: "https://indeed.com/jobs/456",
						found_at: TIMESTAMPS.crossSourceFound,
					},
				],
			},
			company_url: "https://acme.com",
			source_url: "https://linkedin.com/jobs/98765",
			apply_url: "https://acme.com/careers/apply/98765",
			location: "San Francisco, CA",
			work_model: "Remote",
			seniority_level: "Senior",
			salary_min: 150000,
			salary_max: 200000,
			salary_currency: "USD",
			culture_text: "We value collaboration and innovation.",
			requirements: "5+ years Python, FastAPI experience preferred.",
			years_experience_min: 5,
			years_experience_max: 10,
			posted_date: TIMESTAMPS.posted,
			application_deadline: TIMESTAMPS.deadline,
			status: "Applied",
			is_favorite: true,
			fit_score: 85,
			stretch_score: 72,
			score_details: {
				fit: SAMPLE_FIT,
				stretch: SAMPLE_STRETCH,
				explanation: SAMPLE_EXPLANATION,
			},
			ghost_score: 42,
			ghost_signals: {
				days_open: 45,
				days_open_score: 50,
				repost_count: 2,
				repost_score: 60,
				vagueness_score: 30,
				missing_fields: ["salary"],
				missing_fields_score: 33,
				requirement_mismatch: false,
				requirement_mismatch_score: 0,
				calculated_at: TIMESTAMPS.ghostCalculated,
				ghost_score: 42,
			},
			repost_count: 2,
			previous_posting_ids: [IDS.previousPosting1, IDS.previousPosting2],
			last_verified_at: TIMESTAMPS.lastVerified,
		});

		expect(job.external_id).toBe("linkedin-98765");
		expect(job.work_model).toBe("Remote");
		expect(job.seniority_level).toBe("Senior");
		expect(job.salary_min).toBe(150000);
		expect(job.fit_score).toBe(85);
		expect(job.stretch_score).toBe(72);
		expect(job.score_details?.fit.total).toBe(85);
		expect(job.ghost_score).toBe(42);
		expect(job.also_found_on.sources).toHaveLength(1);
		expect(job.previous_posting_ids).toHaveLength(2);
	});

	it("represents a dismissed job with failed non-negotiables", () => {
		const job = makeJobPosting({
			job_title: "Junior Developer",
			company_name: "Startup Inc",
			seniority_level: "Entry",
			description: "Entry level position...",
			status: "Dismissed",
			failed_non_negotiables: [
				{
					filter: FILTER_NAMES.minimumBaseSalary,
					job_value: null,
					persona_value: 80000,
				},
			],
			description_hash: HASHES.description2,
			dismissed_at: TIMESTAMPS.dismissed,
		});

		expect(job.status).toBe("Dismissed");
		expect(job.dismissed_at).toBe(TIMESTAMPS.dismissed);
		expect(job.failed_non_negotiables).toHaveLength(1);
		expect(job.failed_non_negotiables?.[0].filter).toBe(
			FILTER_NAMES.minimumBaseSalary,
		);
	});

	it("uses WorkModel from persona types for work_model field", () => {
		const job = makeJobPosting({ work_model: "Hybrid" });

		expect(job.work_model).toBe("Hybrid");
	});
});
