import { expect, test } from "./base-test";

test("homepage loads successfully", async ({ page }) => {
	await page.goto("/dashboard");
	await expect(page).toHaveTitle("Zentropy Scout");
});
