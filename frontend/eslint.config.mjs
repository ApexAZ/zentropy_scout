import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import prettierConfig from "eslint-config-prettier";
import jsxA11y from "eslint-plugin-jsx-a11y";

// Extract only rules from jsx-a11y recommended (the plugin is already
// registered by eslint-config-next, so we cannot re-register it).
const { rules: a11yRules } = jsxA11y.flatConfigs.recommended;

const eslintConfig = defineConfig([
	...nextVitals,
	...nextTs,
	// Full jsx-a11y recommended ruleset (REQ-012 §13.8).
	// Next.js only enables 6 of 33 rules by default.
	{
		rules: {
			...a11yRules,
			"@typescript-eslint/no-unused-vars": [
				"warn",
				{ argsIgnorePattern: "^_" },
			],
			"react-hooks/incompatible-library": "off",
			// Recognize Radix Checkbox as a form control so
			// <label><Checkbox /></label> doesn't trigger false positives.
			"jsx-a11y/label-has-associated-control": [
				"error",
				{ controlComponents: ["Checkbox"], depth: 5 },
			],
		},
	},
	// Disable ESLint formatting rules that conflict with Prettier.
	prettierConfig,
	// Override default ignores of eslint-config-next.
	globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);

export default eslintConfig;
