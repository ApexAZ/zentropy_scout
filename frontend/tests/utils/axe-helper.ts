/**
 * Reusable axe-core accessibility audit helper for Playwright E2E tests.
 *
 * REQ-012 §13.8: Global accessibility requirements — WCAG 2.1 AA compliance.
 * Wraps @axe-core/playwright's AxeBuilder with sensible defaults for the
 * Zentropy Scout frontend.
 *
 * @example
 * ```ts
 * import { runAxeAudit } from "../utils/axe-helper";
 *
 * test("page is accessible", async ({ page }) => {
 *   await page.goto("/dashboard");
 *   const results = await runAxeAudit(page);
 *   expect(results.violations).toEqual([]);
 * });
 *
 * // With options: skip color-contrast, exclude third-party widgets
 * const results = await runAxeAudit(page, {
 *   disableRules: ["color-contrast"],
 *   exclude: [".third-party-widget"],
 * });
 * ```
 */

import AxeBuilder from "@axe-core/playwright";
import type { AxeResults } from "axe-core";
import type { Page } from "@playwright/test";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * Options for customizing an axe-core accessibility audit.
 */
export interface AxeAuditOptions {
	/** Rule IDs to skip (e.g., `["color-contrast"]`). */
	disableRules?: string[];
	/** CSS selectors to exclude from analysis (e.g., `["nav", ".tooltip"]`). */
	exclude?: string[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * WCAG 2.1 Level AA tag set — the target compliance level for Zentropy Scout.
 * Includes both WCAG 2.0 A/AA and WCAG 2.1 A/AA rules.
 */
export const WCAG_21_AA_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

/**
 * Run an axe-core accessibility audit against the current page state.
 *
 * Defaults to WCAG 2.1 Level AA rules. The page must already be navigated
 * and in a stable state (use `waitForLoadState("networkidle")` or
 * `waitForSelector()` before calling).
 *
 * @param page - Playwright Page object (already navigated to target URL)
 * @param options - Optional overrides for disabled rules and excluded selectors
 * @returns axe-core AxeResults with violations, passes, incomplete, inapplicable
 */
export async function runAxeAudit(
	page: Page,
	options?: AxeAuditOptions,
): Promise<AxeResults> {
	let builder = new AxeBuilder({ page }).withTags(WCAG_21_AA_TAGS);

	if (options?.disableRules?.length) {
		builder = builder.disableRules(options.disableRules);
	}

	if (options?.exclude?.length) {
		for (const selector of options.exclude) {
			builder = builder.exclude(selector);
		}
	}

	return builder.analyze();
}
