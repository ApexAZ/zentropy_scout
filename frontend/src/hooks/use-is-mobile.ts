/**
 * Hook to detect mobile viewport.
 *
 * REQ-012 §4.5: Mobile breakpoint at 768px.
 * Returns true when viewport width is below 768px.
 * SSR-safe — returns false when matchMedia is unavailable.
 */

import { useMediaQuery } from "./use-media-query";

const MOBILE_QUERY = "(max-width: 767px)";

export function useIsMobile(): boolean {
	return useMediaQuery(MOBILE_QUERY);
}
