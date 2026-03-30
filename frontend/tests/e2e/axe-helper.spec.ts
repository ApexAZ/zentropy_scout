/**
 * E2E tests verifying the axe-core audit helper works correctly.
 *
 * REQ-012 §13.8: Global accessibility requirements — WCAG 2.1 AA compliance.
 * Tests the runAxeAudit() helper function itself, not specific page compliance.
 */

import { expect, test } from "./base-test";

import type { AxeAuditOptions } from "../utils/axe-helper";
import { WCAG_21_AA_TAGS, runAxeAudit } from "../utils/axe-helper";
import { setupOnboardedUserMocks } from "../utils/onboarding-api-mocks";

// ---------------------------------------------------------------------------
// A. Helper — Basic Functionality (4 tests)
// ---------------------------------------------------------------------------

test.describe("Axe Audit Helper", () => {
	test.beforeEach(async ({ page }) => {
		await setupOnboardedUserMocks(page);
		await page.goto("/dashboard");
		await page.waitForLoadState("networkidle");
	});

	test("returns AxeResults with violations array for a page", async ({
		page,
	}) => {
		const results = await runAxeAudit(page);

		// AxeResults shape: violations, passes, incomplete, inapplicable
		expect(results).toHaveProperty("violations");
		expect(results).toHaveProperty("passes");
		expect(results).toHaveProperty("incomplete");
		expect(results).toHaveProperty("inapplicable");
		expect(Array.isArray(results.violations)).toBe(true);
	});

	test("applies WCAG 2.1 AA tags by default", async ({ page }) => {
		const results = await runAxeAudit(page);

		// Every reported rule (pass or violation) should have at least one
		// WCAG 2.1 AA tag, confirming the tag filter was applied.
		const allResults = [...results.passes, ...results.violations];

		for (const result of allResults) {
			const hasWcagTag = result.tags.some((tag) =>
				WCAG_21_AA_TAGS.includes(tag),
			);
			expect(hasWcagTag).toBe(true);
		}
	});

	test("accepts disableRules option to skip specific rules", async ({
		page,
	}) => {
		const options: AxeAuditOptions = {
			disableRules: ["color-contrast"],
		};
		const results = await runAxeAudit(page, options);

		// color-contrast should not appear in any result category
		const allRuleIds = [
			...results.passes.map((r) => r.id),
			...results.violations.map((r) => r.id),
			...results.incomplete.map((r) => r.id),
			...results.inapplicable.map((r) => r.id),
		];
		expect(allRuleIds).not.toContain("color-contrast");
	});

	test("accepts exclude option to skip specific selectors", async ({
		page,
	}) => {
		const options: AxeAuditOptions = {
			exclude: ["nav"],
		};
		const results = await runAxeAudit(page, options);

		// No violation node should target an element inside the excluded nav
		for (const violation of results.violations) {
			for (const node of violation.nodes) {
				expect(node.target.join(" ")).not.toContain("nav");
			}
		}
	});
});
