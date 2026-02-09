import { describe, expect, it } from "vitest";

import type {
	AchievementStory,
	Bullet,
	Certification,
	CustomNonNegotiable,
	Education,
	Persona,
	PersonaChangeFlag,
	Skill,
	VoiceProfile,
	WorkHistory,
} from "./persona";
import {
	CHANGE_FLAG_RESOLUTIONS,
	CHANGE_FLAG_STATUSES,
	CHANGE_TYPES,
	COMPANY_SIZE_PREFERENCES,
	FILTER_TYPES,
	MAX_TRAVEL_PERCENTS,
	POLLING_FREQUENCIES,
	PROFICIENCIES,
	REMOTE_PREFERENCES,
	STRETCH_APPETITES,
	WORK_MODELS,
} from "./persona";

/** Fixture IDs to avoid S1192 duplicated string literals. */
const IDS = {
	persona: "660e8400-e29b-41d4-a716-446655440000",
	persona2: "660e8400-e29b-41d4-a716-446655440001",
	user: "ff0e8400-e29b-41d4-a716-446655440000",
	workHistory: "550e8400-e29b-41d4-a716-446655440000",
	bullet: "770e8400-e29b-41d4-a716-446655440000",
	skill: "880e8400-e29b-41d4-a716-446655440000",
	skill2: "880e8400-e29b-41d4-a716-446655440001",
	skillRef: "990e8400-e29b-41d4-a716-446655440000",
	edu: "aa1e8400-e29b-41d4-a716-446655440000",
	edu2: "aa1e8400-e29b-41d4-a716-446655440001",
	cert: "bb1e8400-e29b-41d4-a716-446655440000",
	cert2: "bb1e8400-e29b-41d4-a716-446655440001",
	story: "cc1e8400-e29b-41d4-a716-446655440000",
	story2: "cc1e8400-e29b-41d4-a716-446655440001",
	voice: "dd1e8400-e29b-41d4-a716-446655440000",
	voice2: "dd1e8400-e29b-41d4-a716-446655440001",
	filter: "ee1e8400-e29b-41d4-a716-446655440000",
	filter2: "ee1e8400-e29b-41d4-a716-446655440001",
	flag: "ff1e8400-e29b-41d4-a716-446655440000",
	flag2: "ff1e8400-e29b-41d4-a716-446655440001",
} as const;

const TIMESTAMPS = {
	created: "2025-01-15T10:00:00Z",
	updated: "2025-02-01T14:30:00Z",
	flagCreated: "2025-02-01T10:00:00Z",
	flagResolved: "2025-02-02T09:00:00Z",
	personaCreated: "2025-01-01T00:00:00Z",
	personaUpdated: "2025-02-09T12:00:00Z",
	persona2Created: "2025-02-09T00:00:00Z",
} as const;

describe("Persona Domain Types", () => {
	describe("WorkHistory", () => {
		it("represents a current job", () => {
			const job: WorkHistory = {
				id: IDS.workHistory,
				persona_id: IDS.persona,
				company_name: "Acme Corp",
				company_industry: "Technology",
				job_title: "Senior Developer",
				start_date: "2022-03-01",
				end_date: null,
				is_current: true,
				location: "Austin, TX",
				work_model: "Remote",
				description: "Leading backend development",
				display_order: 0,
				bullets: [],
			};

			expect(job.is_current).toBe(true);
			expect(job.end_date).toBeNull();
			expect(job.work_model).toBe("Remote");
		});

		it("represents a past job with bullets", () => {
			const job: WorkHistory = {
				id: IDS.workHistory,
				persona_id: IDS.persona,
				company_name: "OldCo",
				company_industry: null,
				job_title: "Junior Developer",
				start_date: "2019-01-01",
				end_date: "2022-02-28",
				is_current: false,
				location: "Denver, CO",
				work_model: "Onsite",
				description: null,
				display_order: 1,
				bullets: [
					{
						id: IDS.bullet,
						work_history_id: IDS.workHistory,
						text: "Built REST API serving 10k requests/day",
						skills_demonstrated: [IDS.skill],
						metrics: "10k req/day",
						display_order: 0,
					},
				],
			};

			expect(job.bullets).toHaveLength(1);
			expect(job.bullets[0].metrics).toBe("10k req/day");
		});
	});

	describe("Bullet", () => {
		it("represents an accomplishment with skills and metrics", () => {
			const bullet: Bullet = {
				id: IDS.bullet,
				work_history_id: IDS.workHistory,
				text: "Reduced page load time by 40%",
				skills_demonstrated: [IDS.skill, IDS.skillRef],
				metrics: "40% reduction",
				display_order: 0,
			};

			expect(bullet.skills_demonstrated).toHaveLength(2);
			expect(bullet.metrics).toBe("40% reduction");
		});

		it("allows null metrics and empty skills", () => {
			const bullet: Bullet = {
				id: IDS.bullet,
				work_history_id: IDS.workHistory,
				text: "Mentored junior developers",
				skills_demonstrated: [],
				metrics: null,
				display_order: 1,
			};

			expect(bullet.metrics).toBeNull();
			expect(bullet.skills_demonstrated).toEqual([]);
		});
	});

	describe("Skill", () => {
		it("represents a hard skill", () => {
			const skill: Skill = {
				id: IDS.skill,
				persona_id: IDS.persona,
				skill_name: "TypeScript",
				skill_type: "Hard",
				category: "Programming Language",
				proficiency: "Expert",
				years_used: 5,
				last_used: "Current",
				display_order: 0,
			};

			expect(skill.skill_type).toBe("Hard");
			expect(skill.proficiency).toBe("Expert");
		});

		it("represents a soft skill", () => {
			const skill: Skill = {
				id: IDS.skill2,
				persona_id: IDS.persona,
				skill_name: "Technical Communication",
				skill_type: "Soft",
				category: "Communication",
				proficiency: "Proficient",
				years_used: 8,
				last_used: "Current",
				display_order: 1,
			};

			expect(skill.skill_type).toBe("Soft");
			expect(skill.category).toBe("Communication");
		});
	});

	describe("Education", () => {
		it("represents a degree with optional fields", () => {
			const edu: Education = {
				id: IDS.edu,
				persona_id: IDS.persona,
				institution: "State University",
				degree: "B.S.",
				field_of_study: "Computer Science",
				graduation_year: 2019,
				gpa: 3.87,
				honors: "Cum Laude",
				display_order: 0,
			};

			expect(edu.gpa).toBe(3.87);
			expect(edu.honors).toBe("Cum Laude");
		});

		it("allows null gpa and honors", () => {
			const edu: Education = {
				id: IDS.edu2,
				persona_id: IDS.persona,
				institution: "Online Academy",
				degree: "Certificate",
				field_of_study: "Data Science",
				graduation_year: 2023,
				gpa: null,
				honors: null,
				display_order: 1,
			};

			expect(edu.gpa).toBeNull();
			expect(edu.honors).toBeNull();
		});
	});

	describe("Certification", () => {
		it("represents a certification with expiration", () => {
			const cert: Certification = {
				id: IDS.cert,
				persona_id: IDS.persona,
				certification_name: "AWS Solutions Architect",
				issuing_organization: "Amazon Web Services",
				date_obtained: "2023-06-15",
				expiration_date: "2026-06-15",
				credential_id: "AWS-SA-12345",
				verification_url: "https://aws.amazon.com/verify/12345",
				display_order: 0,
			};

			expect(cert.expiration_date).toBe("2026-06-15");
			expect(cert.credential_id).toBe("AWS-SA-12345");
		});

		it("allows null expiration and optional fields", () => {
			const cert: Certification = {
				id: IDS.cert2,
				persona_id: IDS.persona,
				certification_name: "PMP",
				issuing_organization: "PMI",
				date_obtained: "2022-01-10",
				expiration_date: null,
				credential_id: null,
				verification_url: null,
				display_order: 1,
			};

			expect(cert.expiration_date).toBeNull();
		});
	});

	describe("AchievementStory", () => {
		it("represents a STAR story linked to a job", () => {
			const story: AchievementStory = {
				id: IDS.story,
				persona_id: IDS.persona,
				title: "Led API Migration",
				context: "Legacy monolith was limiting feature velocity.",
				action: "Designed microservice architecture and led 3-person team.",
				outcome: "Reduced deploy time from 2 hours to 15 minutes.",
				skills_demonstrated: [IDS.skill],
				related_job_id: IDS.workHistory,
				display_order: 0,
			};

			expect(story.title).toBe("Led API Migration");
			expect(story.related_job_id).not.toBeNull();
		});

		it("allows null related_job_id and empty skills", () => {
			const story: AchievementStory = {
				id: IDS.story2,
				persona_id: IDS.persona,
				title: "Community Workshop",
				context: "Local meetup needed speakers.",
				action: "Prepared and delivered 3 workshops on React.",
				outcome: "60+ attendees, invited back quarterly.",
				skills_demonstrated: [],
				related_job_id: null,
				display_order: 1,
			};

			expect(story.related_job_id).toBeNull();
			expect(story.skills_demonstrated).toEqual([]);
		});
	});

	describe("VoiceProfile", () => {
		it("represents a writing voice with all fields", () => {
			const voice: VoiceProfile = {
				id: IDS.voice,
				persona_id: IDS.persona,
				tone: "Direct, confident, avoids buzzwords",
				sentence_style: "Short sentences, active voice",
				vocabulary_level: "Technical when relevant, otherwise plain",
				personality_markers: "Dry humor, data-driven",
				sample_phrases: ["Shipped to production", "Cross-functional"],
				things_to_avoid: ["synergy", "leverage", "circle back"],
				writing_sample_text: "I built a system that...",
				created_at: TIMESTAMPS.created,
				updated_at: TIMESTAMPS.updated,
			};

			expect(voice.tone).toBe("Direct, confident, avoids buzzwords");
			expect(voice.things_to_avoid).toContain("synergy");
		});

		it("allows null optional fields", () => {
			const voice: VoiceProfile = {
				id: IDS.voice2,
				persona_id: IDS.persona,
				tone: "Friendly, approachable",
				sentence_style: "Conversational, medium length",
				vocabulary_level: "Non-technical",
				personality_markers: null,
				sample_phrases: [],
				things_to_avoid: [],
				writing_sample_text: null,
				created_at: TIMESTAMPS.created,
				updated_at: TIMESTAMPS.created,
			};

			expect(voice.personality_markers).toBeNull();
			expect(voice.writing_sample_text).toBeNull();
		});
	});

	describe("CustomNonNegotiable", () => {
		it("represents an exclusion filter", () => {
			const filter: CustomNonNegotiable = {
				id: IDS.filter,
				persona_id: IDS.persona,
				filter_name: "No Amazon subsidiaries",
				filter_type: "Exclude",
				filter_value: "Amazon, AWS, Twitch",
				filter_field: "company_name",
			};

			expect(filter.filter_type).toBe("Exclude");
		});

		it("represents a requirement filter", () => {
			const filter: CustomNonNegotiable = {
				id: IDS.filter2,
				persona_id: IDS.persona,
				filter_name: "Must mention TypeScript",
				filter_type: "Require",
				filter_value: "TypeScript",
				filter_field: "description",
			};

			expect(filter.filter_type).toBe("Require");
		});
	});

	describe("PersonaChangeFlag", () => {
		it("represents a pending change flag", () => {
			const flag: PersonaChangeFlag = {
				id: IDS.flag,
				persona_id: IDS.persona,
				change_type: "skill_added",
				item_id: IDS.skill,
				item_description: "TypeScript — Expert",
				status: "Pending",
				resolution: null,
				resolved_at: null,
				created_at: TIMESTAMPS.flagCreated,
			};

			expect(flag.status).toBe("Pending");
			expect(flag.resolution).toBeNull();
		});

		it("represents a resolved change flag", () => {
			const flag: PersonaChangeFlag = {
				id: IDS.flag2,
				persona_id: IDS.persona,
				change_type: "job_added",
				item_id: IDS.workHistory,
				item_description: "Senior Developer at Acme Corp",
				status: "Resolved",
				resolution: "added_to_all",
				resolved_at: TIMESTAMPS.flagResolved,
				created_at: TIMESTAMPS.flagCreated,
			};

			expect(flag.status).toBe("Resolved");
			expect(flag.resolution).toBe("added_to_all");
			expect(flag.resolved_at).not.toBeNull();
		});
	});

	describe("Persona", () => {
		it("represents a full persona with all required fields", () => {
			const persona: Persona = {
				id: IDS.persona,
				user_id: IDS.user,
				full_name: "Jane Smith",
				email: "jane@example.com",
				phone: "512-555-0100",
				home_city: "Austin",
				home_state: "Texas",
				home_country: "United States",
				linkedin_url: "https://linkedin.com/in/janesmith",
				portfolio_url: null,
				professional_summary: "Full-stack engineer with 10 years experience.",
				years_experience: 10,
				current_role: "Senior Engineer",
				current_company: "TechCo",
				target_roles: ["Staff Engineer", "Engineering Manager"],
				target_skills: ["System Design", "Kubernetes"],
				stretch_appetite: "Medium",
				commutable_cities: ["Austin, TX"],
				max_commute_minutes: 30,
				remote_preference: "Hybrid OK",
				relocation_open: false,
				relocation_cities: [],
				minimum_base_salary: 180000,
				salary_currency: "USD",
				visa_sponsorship_required: false,
				industry_exclusions: ["Defense", "Gambling"],
				company_size_preference: "Mid-size",
				max_travel_percent: "<25%",
				minimum_fit_threshold: 50,
				auto_draft_threshold: 90,
				polling_frequency: "Daily",
				onboarding_complete: true,
				onboarding_step: null,
				created_at: TIMESTAMPS.personaCreated,
				updated_at: TIMESTAMPS.personaUpdated,
			};

			expect(persona.full_name).toBe("Jane Smith");
			expect(persona.stretch_appetite).toBe("Medium");
			expect(persona.remote_preference).toBe("Hybrid OK");
			expect(persona.onboarding_complete).toBe(true);
		});

		it("represents a persona with minimal optional fields", () => {
			const persona: Persona = {
				id: IDS.persona2,
				user_id: IDS.user,
				full_name: "John Doe",
				email: "john@example.com",
				phone: "555-0101",
				home_city: "Denver",
				home_state: "Colorado",
				home_country: "United States",
				linkedin_url: null,
				portfolio_url: null,
				professional_summary: null,
				years_experience: null,
				current_role: null,
				current_company: null,
				target_roles: [],
				target_skills: [],
				stretch_appetite: "Low",
				commutable_cities: [],
				max_commute_minutes: null,
				remote_preference: "Remote Only",
				relocation_open: false,
				relocation_cities: [],
				minimum_base_salary: null,
				salary_currency: "USD",
				visa_sponsorship_required: false,
				industry_exclusions: [],
				company_size_preference: "No Preference",
				max_travel_percent: "Any",
				minimum_fit_threshold: 50,
				auto_draft_threshold: 90,
				polling_frequency: "Daily",
				onboarding_complete: false,
				onboarding_step: "basic_info",
				created_at: TIMESTAMPS.persona2Created,
				updated_at: TIMESTAMPS.persona2Created,
			};

			expect(persona.onboarding_complete).toBe(false);
			expect(persona.onboarding_step).toBe("basic_info");
			expect(persona.professional_summary).toBeNull();
		});
	});

	describe("Enum value arrays", () => {
		it("exports WORK_MODELS with all valid values", () => {
			expect(WORK_MODELS).toEqual(["Remote", "Hybrid", "Onsite"]);
		});

		it("exports PROFICIENCIES in ascending order", () => {
			expect(PROFICIENCIES).toEqual([
				"Learning",
				"Familiar",
				"Proficient",
				"Expert",
			]);
		});

		it("exports REMOTE_PREFERENCES with all valid values", () => {
			expect(REMOTE_PREFERENCES).toEqual([
				"Remote Only",
				"Hybrid OK",
				"Onsite OK",
				"No Preference",
			]);
		});

		it("exports COMPANY_SIZE_PREFERENCES with all valid values", () => {
			expect(COMPANY_SIZE_PREFERENCES).toEqual([
				"Startup",
				"Mid-size",
				"Enterprise",
				"No Preference",
			]);
		});

		it("exports MAX_TRAVEL_PERCENTS with all valid values", () => {
			expect(MAX_TRAVEL_PERCENTS).toEqual(["None", "<25%", "<50%", "Any"]);
		});

		it("exports STRETCH_APPETITES with all valid values", () => {
			expect(STRETCH_APPETITES).toEqual(["Low", "Medium", "High"]);
		});

		it("exports POLLING_FREQUENCIES with all valid values", () => {
			expect(POLLING_FREQUENCIES).toEqual([
				"Daily",
				"Twice Daily",
				"Weekly",
				"Manual Only",
			]);
		});

		it("exports FILTER_TYPES with all valid values", () => {
			expect(FILTER_TYPES).toEqual(["Exclude", "Require"]);
		});

		it("exports CHANGE_TYPES with all valid values", () => {
			expect(CHANGE_TYPES).toEqual([
				"job_added",
				"bullet_added",
				"skill_added",
				"education_added",
				"certification_added",
			]);
		});

		it("exports CHANGE_FLAG_STATUSES with all valid values", () => {
			expect(CHANGE_FLAG_STATUSES).toEqual(["Pending", "Resolved"]);
		});

		it("exports CHANGE_FLAG_RESOLUTIONS with all valid values", () => {
			expect(CHANGE_FLAG_RESOLUTIONS).toEqual([
				"added_to_all",
				"added_to_some",
				"skipped",
			]);
		});
	});
});
