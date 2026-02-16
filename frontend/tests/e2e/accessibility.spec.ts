import { expect, test } from "@playwright/test";

import { setupOnboardedUserMocks } from "../utils/onboarding-api-mocks";

test.describe("Reduced Motion", () => {
	test("suppresses animations when prefers-reduced-motion is reduce", async ({
		page,
	}) => {
		await page.emulateMedia({ reducedMotion: "reduce" });
		await setupOnboardedUserMocks(page);
		await page.goto("/");

		// Wait for the page to be fully loaded
		await page.waitForLoadState("networkidle");

		// Verify the media query is active
		const mediaQueryMatches = await page.evaluate(
			() => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
		);
		expect(mediaQueryMatches).toBe(true);

		// Verify CSS rule applies to page elements: set a long transition on
		// body and check the computed value is overridden to near-zero.
		const duration = await page.evaluate(() => {
			document.body.style.transitionProperty = "opacity";
			document.body.style.transitionDuration = "5s";
			// Force style recalc
			void getComputedStyle(document.body).transitionDuration;
			return getComputedStyle(document.body).transitionDuration;
		});

		// 0.01ms = 0.00001s; parseFloat("0.00001s") = 0.00001
		// The !important rule overrides inline styles to near-zero.
		expect(parseFloat(duration)).toBeLessThan(0.01);
	});
});
