/**
 * Hook to detect mobile viewport.
 *
 * REQ-012 §4.5: Mobile breakpoint at 768px.
 * Returns true when viewport width is below 768px.
 * SSR-safe — returns false when matchMedia is unavailable.
 *
 * @module hooks/use-is-mobile
 * @coordinates-with hooks/use-media-query (generic media query hook — sole dependency),
 *   components/layout/chat-sidebar (responsive layout switching),
 *   components/ui/reorderable-list (touch-drag threshold detection)
 */

import { useMediaQuery } from "./use-media-query";

const MOBILE_QUERY = "(max-width: 767px)";

export function useIsMobile(): boolean {
	return useMediaQuery(MOBILE_QUERY);
}
