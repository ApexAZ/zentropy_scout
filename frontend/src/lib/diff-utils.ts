/**
 * Diff utilities for the variant review page (§8.6).
 *
 * REQ-012 §9.3: Changed text highlighted with color.
 * Moved bullets shown with position indicators.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DiffToken {
	text: string;
	type: "same" | "added" | "removed";
}

// ---------------------------------------------------------------------------
// Word-level diff
// ---------------------------------------------------------------------------

/**
 * Compute word-level diff between base and variant strings.
 *
 * Uses Longest Common Subsequence (LCS) to identify same/added/removed words.
 * Returns a flat token array suitable for rendering diff highlights.
 */
export function computeWordDiff(base: string, variant: string): DiffToken[] {
	const baseWords = base.split(/\s+/).filter((w) => w.length > 0);
	const variantWords = variant.split(/\s+/).filter((w) => w.length > 0);

	const m = baseWords.length;
	const n = variantWords.length;

	if (m === 0 && n === 0) return [];

	// Build LCS table
	const dp: number[][] = Array.from({ length: m + 1 }, () =>
		new Array<number>(n + 1).fill(0),
	);

	for (let i = 1; i <= m; i++) {
		for (let j = 1; j <= n; j++) {
			if (baseWords[i - 1] === variantWords[j - 1]) {
				dp[i][j] = dp[i - 1][j - 1] + 1;
			} else {
				dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
			}
		}
	}

	// Backtrack to produce diff tokens (in reverse)
	const reversed: DiffToken[] = [];
	let i = m;
	let j = n;

	while (i > 0 || j > 0) {
		if (i > 0 && j > 0 && baseWords[i - 1] === variantWords[j - 1]) {
			reversed.push({ text: baseWords[i - 1], type: "same" });
			i--;
			j--;
		} else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
			reversed.push({ text: variantWords[j - 1], type: "added" });
			j--;
		} else {
			reversed.push({ text: baseWords[i - 1], type: "removed" });
			i--;
		}
	}

	return reversed.reverse();
}

// ---------------------------------------------------------------------------
// Bullet move detection
// ---------------------------------------------------------------------------

/**
 * Compute which bullets moved between base and variant order.
 * Returns a Map of bulletId → original 1-based position for moved bullets.
 * Bullets not present in base are ignored (new bullets).
 */
export function computeBulletMoves(
	baseOrder: string[],
	variantOrder: string[],
): Map<string, number> {
	const moves = new Map<string, number>();

	for (let varIdx = 0; varIdx < variantOrder.length; varIdx++) {
		const bulletId = variantOrder[varIdx];
		const baseIdx = baseOrder.indexOf(bulletId);
		if (baseIdx !== -1 && baseIdx !== varIdx) {
			moves.set(bulletId, baseIdx + 1); // 1-based
		}
	}

	return moves;
}
