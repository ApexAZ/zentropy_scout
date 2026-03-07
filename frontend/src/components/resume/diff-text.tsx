"use client";

/**
 * Inline word-level diff text for structured resume comparison.
 *
 * Renders diff tokens with color highlighting, filtering by side
 * (base shows removals, variant shows additions).
 */

import type { DiffToken } from "@/lib/diff-utils";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DIFF_CLASS_MAP: Readonly<Record<string, string | undefined>> = {
	same: undefined,
	added: "text-success font-medium",
	removed: "text-destructive line-through",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DiffText({
	tokens,
	side,
}: Readonly<{
	tokens: DiffToken[];
	side: "base" | "variant";
}>) {
	const filtered =
		side === "base"
			? tokens.filter((t) => t.type !== "added")
			: tokens.filter((t) => t.type !== "removed");

	return (
		<p className="text-sm leading-relaxed">
			{filtered.map((token, idx) => {
				const diffType = token.type === "same" ? undefined : token.type;
				const className = DIFF_CLASS_MAP[token.type];

				return (
					<span key={`${token.type}-${idx}`}>
						{idx > 0 ? " " : ""}
						<span data-diff={diffType} className={className}>
							{token.text}
						</span>
					</span>
				);
			})}
		</p>
	);
}
