"use client";

/**
 * @fileoverview Pending change flags warning banner with count and review link.
 *
 * Layer: component
 * Feature: persona
 *
 * REQ-012 §7.6: Shows count of pending PersonaChangeFlags with a
 * link to the resolution page. Returns null when there are no
 * pending flags.
 *
 * Coordinates with:
 * - lib/api-client.ts: apiGet for pending change flags fetch
 * - lib/query-keys.ts: queryKeys.changeFlags cache key
 * - types/api.ts: ApiListResponse envelope type
 * - types/persona.ts: PersonaChangeFlag type
 *
 * Called by / Used by:
 * - components/persona/persona-overview.tsx: displayed on persona overview
 */

import { useQuery } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";
import Link from "next/link";

import { apiGet } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { ApiListResponse } from "@/types/api";
import type { PersonaChangeFlag } from "@/types/persona";

export function ChangeFlagsBanner() {
	const { data } = useQuery({
		queryKey: queryKeys.changeFlags,
		queryFn: () =>
			apiGet<ApiListResponse<PersonaChangeFlag>>("/persona-change-flags", {
				status: "Pending",
			}),
	});

	const count = data?.data.length ?? 0;

	if (count === 0) {
		return null;
	}

	const message =
		count === 1 ? "1 change needs review" : `${count} changes need review`;

	return (
		<output
			className="border-warning/50 bg-warning/10 flex items-center justify-between rounded-lg border p-4"
			data-testid="change-flags-banner"
		>
			<div className="flex items-center gap-2 text-sm">
				<TriangleAlert className="text-warning h-4 w-4" />
				<span>{message}</span>
			</div>
			<Link
				href="/persona/change-flags"
				className="text-primary text-sm font-medium hover:underline"
			>
				Review
			</Link>
		</output>
	);
}
