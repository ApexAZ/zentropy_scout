import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import prettierConfig from "eslint-config-prettier";

const eslintConfig = defineConfig([
	...nextVitals,
	...nextTs,
	// Allow underscore-prefixed parameters to satisfy callback signatures
	// where not all arguments are used.
	// Disable react-hooks/incompatible-library — false positives on
	// React Hook Form's watch() API (eslint-plugin-react-hooks v5).
	{
		rules: {
			"@typescript-eslint/no-unused-vars": [
				"warn",
				{ argsIgnorePattern: "^_" },
			],
			"react-hooks/incompatible-library": "off",
		},
	},
	// Disable ESLint formatting rules that conflict with Prettier.
	prettierConfig,
	// Override default ignores of eslint-config-next.
	globalIgnores([
		// Default ignores of eslint-config-next:
		".next/**",
		"out/**",
		"build/**",
		"next-env.d.ts",
	]),
]);

export default eslintConfig;
