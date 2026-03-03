import { expect, test } from "./base-test";

test("homepage loads successfully", async ({ page }) => {
	await page.goto("/");
	await expect(page).toHaveTitle("Zentropy Scout");
});
