/**
 * Hook to detect mobile viewport.
 *
 * REQ-012 §4.5: Mobile breakpoint at 768px.
 * Returns true when viewport width is below 768px.
 * SSR-safe — returns false when matchMedia is unavailable.
 */

import { useEffect, useState } from "react";

const MOBILE_QUERY = "(max-width: 767px)";

export function useIsMobile(): boolean {
	const [isMobile, setIsMobile] = useState(() => {
		if (typeof window === "undefined" || !window.matchMedia) return false;
		return window.matchMedia(MOBILE_QUERY).matches;
	});

	useEffect(() => {
		if (typeof window === "undefined" || !window.matchMedia) return;

		const mql = window.matchMedia(MOBILE_QUERY);

		const handleChange = (
			event: MediaQueryListEvent | { matches: boolean },
		) => {
			setIsMobile(event.matches);
		};

		mql.addEventListener("change", handleChange);
		return () => mql.removeEventListener("change", handleChange);
	}, []);

	return isMobile;
}
