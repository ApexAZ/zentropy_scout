/**
 * Tests for the useResumeContentSelection hook.
 *
 * REQ-012 §9.2: Verifies checkbox state management and toggle handlers
 * for resume content selection (jobs, bullets, education, certifications,
 * skills emphasis).
 */

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { WorkHistory } from "@/types/persona";

import { useResumeContentSelection } from "./use-resume-content-selection";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_JOB: WorkHistory = {
	id: "job-1",
	persona_id: "persona-1",
	company_name: "Acme",
	company_industry: null,
	job_title: "Engineer",
	start_date: "2020-01-01",
	end_date: "2023-06-01",
	is_current: false,
	location: "NYC",
	work_model: "Onsite",
	description: "Built things",
	display_order: 0,
	bullets: [
		{
			id: "b-1",
			work_history_id: "job-1",
			text: "Bullet one",
			skills_demonstrated: [],
			metrics: null,
			display_order: 0,
		},
		{
			id: "b-2",
			work_history_id: "job-1",
			text: "Bullet two",
			skills_demonstrated: [],
			metrics: null,
			display_order: 1,
		},
	],
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useResumeContentSelection", () => {
	it("initializes with empty state", () => {
		const { result } = renderHook(() => useResumeContentSelection());

		expect(result.current.includedJobs).toEqual([]);
		expect(result.current.bulletSelections).toEqual({});
		expect(result.current.bulletOrder).toEqual({});
		expect(result.current.includedEducation).toEqual([]);
		expect(result.current.includedCertifications).toEqual([]);
		expect(result.current.skillsEmphasis).toEqual([]);
	});

	// -----------------------------------------------------------------------
	// Job toggle
	// -----------------------------------------------------------------------

	describe("handleToggleJob", () => {
		it("adds job and selects all bullets", () => {
			const { result } = renderHook(() => useResumeContentSelection());

			act(() => {
				result.current.handleToggleJob("job-1", MOCK_JOB);
			});

			expect(result.current.includedJobs).toEqual(["job-1"]);
			expect(result.current.bulletSelections["job-1"]).toEqual(["b-1", "b-2"]);
			expect(result.current.bulletOrder["job-1"]).toEqual(["b-1", "b-2"]);
		});

		it("removes job and clears bullet selections and order", () => {
			const { result } = renderHook(() => useResumeContentSelection());

			act(() => {
				result.current.handleToggleJob("job-1", MOCK_JOB);
			});

			act(() => {
				result.current.handleToggleJob("job-1", MOCK_JOB);
			});

			expect(result.current.includedJobs).toEqual([]);
			expect(result.current.bulletSelections["job-1"]).toBeUndefined();
			expect(result.current.bulletOrder["job-1"]).toBeUndefined();
		});
	});

	// -----------------------------------------------------------------------
	// Bullet toggle
	// -----------------------------------------------------------------------

	describe("handleToggleBullet", () => {
		it("removes a bullet from selection", () => {
			const { result } = renderHook(() => useResumeContentSelection());

			act(() => {
				result.current.handleToggleJob("job-1", MOCK_JOB);
			});

			act(() => {
				result.current.handleToggleBullet("job-1", "b-1");
			});

			expect(result.current.bulletSelections["job-1"]).toEqual(["b-2"]);
		});

		it("adds a bullet back to selection", () => {
			const { result } = renderHook(() => useResumeContentSelection());

			act(() => {
				result.current.handleToggleJob("job-1", MOCK_JOB);
			});

			act(() => {
				result.current.handleToggleBullet("job-1", "b-1");
			});

			act(() => {
				result.current.handleToggleBullet("job-1", "b-1");
			});

			expect(result.current.bulletSelections["job-1"]).toEqual(["b-2", "b-1"]);
		});
	});

	// -----------------------------------------------------------------------
	// Education toggle
	// -----------------------------------------------------------------------

	describe("handleToggleEducation", () => {
		it("adds and removes education", () => {
			const { result } = renderHook(() => useResumeContentSelection());

			act(() => {
				result.current.handleToggleEducation("edu-1");
			});

			expect(result.current.includedEducation).toEqual(["edu-1"]);

			act(() => {
				result.current.handleToggleEducation("edu-1");
			});

			expect(result.current.includedEducation).toEqual([]);
		});
	});

	// -----------------------------------------------------------------------
	// Certification toggle
	// -----------------------------------------------------------------------

	describe("handleToggleCertification", () => {
		it("adds and removes certification", () => {
			const { result } = renderHook(() => useResumeContentSelection());

			act(() => {
				result.current.handleToggleCertification("cert-1");
			});

			expect(result.current.includedCertifications).toEqual(["cert-1"]);

			act(() => {
				result.current.handleToggleCertification("cert-1");
			});

			expect(result.current.includedCertifications).toEqual([]);
		});
	});

	// -----------------------------------------------------------------------
	// Skill toggle
	// -----------------------------------------------------------------------

	describe("handleToggleSkill", () => {
		it("adds and removes skill", () => {
			const { result } = renderHook(() => useResumeContentSelection());

			act(() => {
				result.current.handleToggleSkill("skill-1");
			});

			expect(result.current.skillsEmphasis).toEqual(["skill-1"]);

			act(() => {
				result.current.handleToggleSkill("skill-1");
			});

			expect(result.current.skillsEmphasis).toEqual([]);
		});
	});

	// -----------------------------------------------------------------------
	// Setters
	// -----------------------------------------------------------------------

	describe("setters", () => {
		it("exposes state setters for external initialization", () => {
			const { result } = renderHook(() => useResumeContentSelection());

			act(() => {
				result.current.setIncludedJobs(["j-1", "j-2"]);
				result.current.setIncludedEducation(["e-1"]);
				result.current.setIncludedCertifications(["c-1"]);
				result.current.setSkillsEmphasis(["s-1"]);
			});

			expect(result.current.includedJobs).toEqual(["j-1", "j-2"]);
			expect(result.current.includedEducation).toEqual(["e-1"]);
			expect(result.current.includedCertifications).toEqual(["c-1"]);
			expect(result.current.skillsEmphasis).toEqual(["s-1"]);
		});
	});
});
