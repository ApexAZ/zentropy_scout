/**
 * Shared helpers for resume components.
 *
 * REQ-012 §9.2-9.3: Utilities used by base resume detail and
 * variant review for bullet ordering.
 *
 * @module lib/resume-helpers
 * @coordinates-with types/persona (Bullet type — sorted by these helpers),
 *   components/resume/resume-detail (base resume bullet ordering),
 *   components/resume/variant-review (variant bullet ordering + diff)
 */

import type { Bullet } from "@/types/persona";

/** Sort bullets according to a specified order. Unordered bullets go to end. */
export function orderBullets(
	bullets: Bullet[],
	order: string[] | undefined,
): Bullet[] {
	if (!order || order.length === 0) return bullets;
	return [...bullets].sort((a, b) => {
		const aIdx = order.indexOf(a.id);
		const bIdx = order.indexOf(b.id);
		return (aIdx === -1 ? Infinity : aIdx) - (bIdx === -1 ? Infinity : bIdx);
	});
}
