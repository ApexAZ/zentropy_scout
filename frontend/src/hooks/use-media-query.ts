/**
 * @fileoverview Generic media query hook.
 *
 * Layer: hook
 * Feature: shared
 *
 * REQ-012 §5.1: Responsive breakpoint detection.
 * SSR-safe — returns false when matchMedia is unavailable.
 *
 * Coordinates with:
 * - (no upstream lib imports — pure DOM hook)
 *
 * Called by / Used by:
 * - hooks/use-is-mobile.ts: primary consumer — mobile breakpoint wrapper
 * - components/layout/chat-sidebar.tsx: responsive sidebar behavior
 */

import { useEffect, useState } from "react";

export function useMediaQuery(query: string): boolean {
	const [matches, setMatches] = useState(() => {
		if (typeof globalThis.matchMedia !== "function") return false;
		return globalThis.matchMedia(query).matches;
	});

	useEffect(() => {
		if (typeof globalThis.matchMedia !== "function") return;

		const mql = globalThis.matchMedia(query);

		const handleChange = (
			event: MediaQueryListEvent | { matches: boolean },
		) => {
			setMatches(event.matches);
		};

		mql.addEventListener("change", handleChange);
		return () => mql.removeEventListener("change", handleChange);
	}, [query]);

	return matches;
}
