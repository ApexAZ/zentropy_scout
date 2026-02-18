/**
 * Shared Playwright test utilities.
 */

import type { Page } from "@playwright/test";

/**
 * Remove React Query DevTools overlay.
 *
 * The TanStack Query DevTools floating toggle renders a fixed-position SVG
 * that intercepts pointer events on elements near the page bottom. Call this
 * before interacting with buttons/links in that region.
 */
export async function removeDevToolsOverlay(page: Page): Promise<void> {
	await page.evaluate(() => {
		document.querySelector(".tsqd-parent-container")?.remove();
	});
}
