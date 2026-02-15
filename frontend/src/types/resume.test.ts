import { describe, expect, it } from "vitest";

import type {
	BaseResume,
	BaseResumeStatus,
	GuardrailResult,
	GuardrailSeverity,
	GuardrailViolation,
	JobVariant,
	JobVariantStatus,
	ResumeFile,
	ResumeFileType,
	ResumeSourceType,
	SubmittedResumePDF,
} from "./resume";
import {
	BASE_RESUME_STATUSES,
	GUARDRAIL_SEVERITIES,
	JOB_VARIANT_STATUSES,
	RESUME_FILE_TYPES,
	RESUME_SOURCE_TYPES,
} from "./resume";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const IDS = {
	resumeFile: "aa0e8400-e29b-41d4-a716-556655440000",
	baseResume: "bb0e8400-e29b-41d4-a716-556655440000",
	jobVariant: "cc0e8400-e29b-41d4-a716-556655440000",
	submittedPdf: "dd0e8400-e29b-41d4-a716-556655440000",
	persona: "ee0e8400-e29b-41d4-a716-556655440000",
	jobPosting: "ff0e8400-e29b-41d4-a716-556655440000",
	application: "110e8400-e29b-41d4-a716-556655440000",
	job1: "220e8400-e29b-41d4-a716-556655440000",
	job2: "330e8400-e29b-41d4-a716-556655440000",
	bullet1: "440e8400-e29b-41d4-a716-556655440000",
	bullet2: "550e8400-e29b-41d4-a716-556655440000",
	bullet3: "660e8400-e29b-41d4-a716-556655440000",
	education1: "770e8400-e29b-41d4-a716-556655440000",
	certification1: "880e8400-e29b-41d4-a716-556655440000",
	skill1: "990e8400-e29b-41d4-a716-556655440000",
	skill2: "aa1e8400-e29b-41d4-a716-556655440000",
} as const;

const TIMESTAMPS = {
	created: "2025-01-15T10:00:00Z",
	updated: "2025-02-01T14:30:00Z",
	uploaded: "2025-01-10T09:00:00Z",
	rendered: "2025-01-20T11:00:00Z",
	approved: "2025-02-05T16:00:00Z",
	archived: "2025-02-06T00:00:00Z",
} as const;

const GUARDRAIL_RULES = {
	newBullets: "new_bullets_added",
	summaryLength: "summary_length_change",
	skillsNotInPersona: "skills_not_in_persona",
} as const;

// ---------------------------------------------------------------------------
// Factory functions
// ---------------------------------------------------------------------------

function makeResumeFile(overrides: Partial<ResumeFile> = {}): ResumeFile {
	return {
		id: IDS.resumeFile,
		persona_id: IDS.persona,
		file_name: "resume_2025.pdf",
		file_type: "PDF",
		file_size_bytes: 524288,
		uploaded_at: TIMESTAMPS.uploaded,
		is_active: true,
		...overrides,
	};
}

function makeBaseResume(overrides: Partial<BaseResume> = {}): BaseResume {
	return {
		id: IDS.baseResume,
		persona_id: IDS.persona,
		name: "Senior Engineer Resume",
		role_type: "Software Engineer",
		summary: "Experienced software engineer...",
		included_jobs: [IDS.job1, IDS.job2],
		included_education: [IDS.education1],
		included_certifications: [IDS.certification1],
		skills_emphasis: [IDS.skill1, IDS.skill2],
		job_bullet_selections: {
			[IDS.job1]: [IDS.bullet1, IDS.bullet2],
			[IDS.job2]: [IDS.bullet3],
		},
		job_bullet_order: {
			[IDS.job1]: [IDS.bullet2, IDS.bullet1],
			[IDS.job2]: [IDS.bullet3],
		},
		rendered_at: TIMESTAMPS.rendered,
		is_primary: true,
		status: "Active",
		display_order: 0,
		archived_at: null,
		created_at: TIMESTAMPS.created,
		updated_at: TIMESTAMPS.updated,
		...overrides,
	};
}

function makeJobVariant(overrides: Partial<JobVariant> = {}): JobVariant {
	return {
		id: IDS.jobVariant,
		base_resume_id: IDS.baseResume,
		job_posting_id: IDS.jobPosting,
		summary: "Tailored summary for this job...",
		job_bullet_order: {
			[IDS.job1]: [IDS.bullet2, IDS.bullet1],
		},
		modifications_description:
			"Reordered bullets to emphasize leadership experience",
		agent_reasoning: null,
		guardrail_result: null,
		status: "Draft",
		snapshot_included_jobs: null,
		snapshot_job_bullet_selections: null,
		snapshot_included_education: null,
		snapshot_included_certifications: null,
		snapshot_skills_emphasis: null,
		approved_at: null,
		archived_at: null,
		created_at: TIMESTAMPS.created,
		updated_at: TIMESTAMPS.updated,
		...overrides,
	};
}

function makeSubmittedResumePDF(
	overrides: Partial<SubmittedResumePDF> = {},
): SubmittedResumePDF {
	return {
		id: IDS.submittedPdf,
		application_id: IDS.application,
		resume_source_type: "Variant",
		resume_source_id: IDS.jobVariant,
		file_name: "Smith_Jane_Resume_Acme_Corp.pdf",
		generated_at: TIMESTAMPS.created,
		...overrides,
	};
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Resume domain types", () => {
	// -----------------------------------------------------------------------
	// Union types
	// -----------------------------------------------------------------------

	describe("ResumeFileType", () => {
		it("accepts valid file types", () => {
			const pdf: ResumeFileType = "PDF";
			const docx: ResumeFileType = "DOCX";
			expect(pdf).toBe("PDF");
			expect(docx).toBe("DOCX");
		});
	});

	describe("BaseResumeStatus", () => {
		it("accepts valid statuses", () => {
			const active: BaseResumeStatus = "Active";
			const archived: BaseResumeStatus = "Archived";
			expect(active).toBe("Active");
			expect(archived).toBe("Archived");
		});
	});

	describe("JobVariantStatus", () => {
		it("accepts valid statuses", () => {
			const draft: JobVariantStatus = "Draft";
			const approved: JobVariantStatus = "Approved";
			const archived: JobVariantStatus = "Archived";
			expect(draft).toBe("Draft");
			expect(approved).toBe("Approved");
			expect(archived).toBe("Archived");
		});
	});

	describe("ResumeSourceType", () => {
		it("accepts valid source types", () => {
			const base: ResumeSourceType = "Base";
			const variant: ResumeSourceType = "Variant";
			expect(base).toBe("Base");
			expect(variant).toBe("Variant");
		});
	});

	describe("GuardrailSeverity", () => {
		it("accepts valid severities", () => {
			const error: GuardrailSeverity = "error";
			const warning: GuardrailSeverity = "warning";
			expect(error).toBe("error");
			expect(warning).toBe("warning");
		});
	});

	// -----------------------------------------------------------------------
	// Value arrays
	// -----------------------------------------------------------------------

	describe("RESUME_FILE_TYPES", () => {
		it("contains all file types", () => {
			expect(RESUME_FILE_TYPES).toEqual(["PDF", "DOCX"]);
		});
	});

	describe("BASE_RESUME_STATUSES", () => {
		it("contains all statuses", () => {
			expect(BASE_RESUME_STATUSES).toEqual(["Active", "Archived"]);
		});
	});

	describe("JOB_VARIANT_STATUSES", () => {
		it("contains all statuses in lifecycle order", () => {
			expect(JOB_VARIANT_STATUSES).toEqual(["Draft", "Approved", "Archived"]);
		});
	});

	describe("RESUME_SOURCE_TYPES", () => {
		it("contains all source types", () => {
			expect(RESUME_SOURCE_TYPES).toEqual(["Base", "Variant"]);
		});
	});

	describe("GUARDRAIL_SEVERITIES", () => {
		it("contains all severities", () => {
			expect(GUARDRAIL_SEVERITIES).toEqual(["error", "warning"]);
		});
	});

	// -----------------------------------------------------------------------
	// Interfaces
	// -----------------------------------------------------------------------

	describe("ResumeFile", () => {
		it("creates a valid resume file", () => {
			const file = makeResumeFile();
			expect(file.id).toBe(IDS.resumeFile);
			expect(file.persona_id).toBe(IDS.persona);
			expect(file.file_name).toBe("resume_2025.pdf");
			expect(file.file_type).toBe("PDF");
			expect(file.file_size_bytes).toBe(524288);
			expect(file.uploaded_at).toBe(TIMESTAMPS.uploaded);
			expect(file.is_active).toBe(true);
		});

		it("supports DOCX file type", () => {
			const file = makeResumeFile({
				file_name: "resume_2025.docx",
				file_type: "DOCX",
			});
			expect(file.file_type).toBe("DOCX");
		});

		it("supports inactive files", () => {
			const file = makeResumeFile({ is_active: false });
			expect(file.is_active).toBe(false);
		});
	});

	describe("BaseResume", () => {
		it("creates a valid base resume with all content selections", () => {
			const resume = makeBaseResume();
			expect(resume.id).toBe(IDS.baseResume);
			expect(resume.persona_id).toBe(IDS.persona);
			expect(resume.name).toBe("Senior Engineer Resume");
			expect(resume.role_type).toBe("Software Engineer");
			expect(resume.summary).toBe("Experienced software engineer...");
			expect(resume.included_jobs).toEqual([IDS.job1, IDS.job2]);
			expect(resume.included_education).toEqual([IDS.education1]);
			expect(resume.included_certifications).toEqual([IDS.certification1]);
			expect(resume.skills_emphasis).toEqual([IDS.skill1, IDS.skill2]);
			expect(resume.is_primary).toBe(true);
			expect(resume.status).toBe("Active");
		});

		it("stores job bullet selections as job-to-bullets mapping", () => {
			const resume = makeBaseResume();
			expect(resume.job_bullet_selections[IDS.job1]).toEqual([
				IDS.bullet1,
				IDS.bullet2,
			]);
			expect(resume.job_bullet_selections[IDS.job2]).toEqual([IDS.bullet3]);
		});

		it("stores job bullet order as job-to-ordered-bullets mapping", () => {
			const resume = makeBaseResume();
			expect(resume.job_bullet_order[IDS.job1]).toEqual([
				IDS.bullet2,
				IDS.bullet1,
			]);
			expect(resume.job_bullet_order[IDS.job2]).toEqual([IDS.bullet3]);
		});

		it("supports null optional fields for show-all behavior", () => {
			const resume = makeBaseResume({
				included_education: null,
				included_certifications: null,
				skills_emphasis: null,
			});
			expect(resume.included_education).toBeNull();
			expect(resume.included_certifications).toBeNull();
			expect(resume.skills_emphasis).toBeNull();
		});

		it("supports archived status", () => {
			const resume = makeBaseResume({
				status: "Archived",
				archived_at: TIMESTAMPS.archived,
			});
			expect(resume.status).toBe("Archived");
			expect(resume.archived_at).toBe(TIMESTAMPS.archived);
		});

		it("tracks render timestamp", () => {
			const resume = makeBaseResume();
			expect(resume.rendered_at).toBe(TIMESTAMPS.rendered);
		});

		it("supports un-rendered state", () => {
			const resume = makeBaseResume({ rendered_at: null });
			expect(resume.rendered_at).toBeNull();
		});
	});

	describe("JobVariant", () => {
		it("creates a valid draft variant", () => {
			const variant = makeJobVariant();
			expect(variant.id).toBe(IDS.jobVariant);
			expect(variant.base_resume_id).toBe(IDS.baseResume);
			expect(variant.job_posting_id).toBe(IDS.jobPosting);
			expect(variant.summary).toBe("Tailored summary for this job...");
			expect(variant.modifications_description).toBe(
				"Reordered bullets to emphasize leadership experience",
			);
			expect(variant.status).toBe("Draft");
			expect(variant.approved_at).toBeNull();
		});

		it("stores job bullet order overrides", () => {
			const variant = makeJobVariant();
			expect(variant.job_bullet_order[IDS.job1]).toEqual([
				IDS.bullet2,
				IDS.bullet1,
			]);
		});

		it("supports approved status with snapshots", () => {
			const variant = makeJobVariant({
				status: "Approved",
				approved_at: TIMESTAMPS.approved,
				snapshot_included_jobs: [IDS.job1, IDS.job2],
				snapshot_job_bullet_selections: {
					[IDS.job1]: [IDS.bullet1, IDS.bullet2],
				},
				snapshot_included_education: [IDS.education1],
				snapshot_included_certifications: [IDS.certification1],
				snapshot_skills_emphasis: [IDS.skill1],
			});
			expect(variant.status).toBe("Approved");
			expect(variant.approved_at).toBe(TIMESTAMPS.approved);
			expect(variant.snapshot_included_jobs).toEqual([IDS.job1, IDS.job2]);
			expect(variant.snapshot_job_bullet_selections).toEqual({
				[IDS.job1]: [IDS.bullet1, IDS.bullet2],
			});
			expect(variant.snapshot_included_education).toEqual([IDS.education1]);
			expect(variant.snapshot_included_certifications).toEqual([
				IDS.certification1,
			]);
			expect(variant.snapshot_skills_emphasis).toEqual([IDS.skill1]);
		});

		it("supports archived status", () => {
			const variant = makeJobVariant({
				status: "Archived",
				archived_at: TIMESTAMPS.archived,
			});
			expect(variant.status).toBe("Archived");
			expect(variant.archived_at).toBe(TIMESTAMPS.archived);
		});

		it("supports null modifications description", () => {
			const variant = makeJobVariant({
				modifications_description: null,
			});
			expect(variant.modifications_description).toBeNull();
		});
	});

	describe("SubmittedResumePDF", () => {
		it("creates a valid submitted PDF from variant", () => {
			const pdf = makeSubmittedResumePDF();
			expect(pdf.id).toBe(IDS.submittedPdf);
			expect(pdf.application_id).toBe(IDS.application);
			expect(pdf.resume_source_type).toBe("Variant");
			expect(pdf.resume_source_id).toBe(IDS.jobVariant);
			expect(pdf.file_name).toBe("Smith_Jane_Resume_Acme_Corp.pdf");
			expect(pdf.generated_at).toBe(TIMESTAMPS.created);
		});

		it("supports base resume as source", () => {
			const pdf = makeSubmittedResumePDF({
				resume_source_type: "Base",
				resume_source_id: IDS.baseResume,
			});
			expect(pdf.resume_source_type).toBe("Base");
			expect(pdf.resume_source_id).toBe(IDS.baseResume);
		});

		it("supports null application ID before submission", () => {
			const pdf = makeSubmittedResumePDF({ application_id: null });
			expect(pdf.application_id).toBeNull();
		});
	});

	describe("GuardrailViolation", () => {
		it("creates a valid error violation", () => {
			const violation: GuardrailViolation = {
				severity: "error",
				rule: GUARDRAIL_RULES.newBullets,
				message:
					"Variant contains bullets not in BaseResume: bullet-1, bullet-2",
			};
			expect(violation.severity).toBe("error");
			expect(violation.rule).toBe(GUARDRAIL_RULES.newBullets);
			expect(violation.message).toContain("not in BaseResume");
		});

		it("creates a valid warning violation", () => {
			const violation: GuardrailViolation = {
				severity: "warning",
				rule: GUARDRAIL_RULES.summaryLength,
				message: "Summary length changed by 15% (max 20%)",
			};
			expect(violation.severity).toBe("warning");
			expect(violation.rule).toBe(GUARDRAIL_RULES.summaryLength);
		});
	});

	describe("GuardrailResult", () => {
		it("creates a passing result with no violations", () => {
			const result: GuardrailResult = {
				passed: true,
				violations: [],
			};
			expect(result.passed).toBe(true);
			expect(result.violations).toHaveLength(0);
		});

		it("creates a failing result with violations", () => {
			const result: GuardrailResult = {
				passed: false,
				violations: [
					{
						severity: "error",
						rule: GUARDRAIL_RULES.newBullets,
						message: "Variant contains bullets not in BaseResume",
					},
					{
						severity: "error",
						rule: GUARDRAIL_RULES.skillsNotInPersona,
						message: "Summary mentions skills not in Persona: Go, Rust",
					},
					{
						severity: "warning",
						rule: GUARDRAIL_RULES.summaryLength,
						message: "Summary length changed by 15% (max 20%)",
					},
				],
			};
			expect(result.passed).toBe(false);
			expect(result.violations).toHaveLength(3);
			expect(
				result.violations.filter((v) => v.severity === "error"),
			).toHaveLength(2);
			expect(
				result.violations.filter((v) => v.severity === "warning"),
			).toHaveLength(1);
		});
	});
});
