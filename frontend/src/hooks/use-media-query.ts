/**
 * Generic media query hook.
 *
 * REQ-012 §5.1: Responsive breakpoint detection.
 * SSR-safe — returns false when matchMedia is unavailable.
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
