import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";
import { defineConfig } from "vitest/config";

export default defineConfig({
	plugins: [tsconfigPaths(), react()],
	test: {
		environment: "jsdom",
		setupFiles: ["./src/test/setup.ts"],
		include: ["src/**/*.test.{ts,tsx}"],
		coverage: {
			provider: "v8",
			reporter: ["text", "lcov"],
			reportsDirectory: "./coverage",
			include: ["src/**/*.{ts,tsx}"],
			exclude: ["src/test/**", "src/**/*.test.{ts,tsx}"],
		},
	},
});
