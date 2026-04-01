/**
 * @fileoverview Hook to detect mobile viewport.
 *
 * Layer: hook
 * Feature: shared
 *
 * REQ-012 §4.5: Mobile breakpoint at 768px.
 * Returns true when viewport width is below 768px.
 * SSR-safe — returns false when matchMedia is unavailable.
 *
 * Coordinates with:
 * - hooks/use-media-query.ts: generic media query hook (sole dependency)
 *
 * Called by / Used by:
 * - components/layout/chat-sidebar.tsx: responsive layout switching
 * - components/ui/reorderable-list.tsx: touch-drag threshold detection
 */

import { useMediaQuery } from "./use-media-query";

const MOBILE_QUERY = "(max-width: 767px)";

export function useIsMobile(): boolean {
	return useMediaQuery(MOBILE_QUERY);
}
