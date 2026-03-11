"use client";

/**
 * Funding pack selection cards with checkout redirect.
 *
 * REQ-029 §9.2: Pack cards with name, description, price, highlight badge.
 * REQ-029 §9.3: Checkout via location.assign redirect (no Stripe JS).
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { createCheckoutSession, fetchCreditPacks } from "@/lib/api/credits";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { PackItem } from "@/types/usage";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FundingPacks() {
	const { data, isLoading } = useQuery({
		queryKey: queryKeys.creditPacks,
		queryFn: fetchCreditPacks,
	});

	const [checkoutPackId, setCheckoutPackId] = useState<string | null>(null);

	async function handleAddFunds(packId: string) {
		setCheckoutPackId(packId);
		try {
			const response = await createCheckoutSession(packId);
			globalThis.location.assign(response.data.checkout_url);
		} catch {
			showToast.error("Unable to start checkout. Please try again.");
			setCheckoutPackId(null);
		}
	}

	if (isLoading) {
		return (
			<div
				id="funding-packs"
				data-testid="funding-packs-skeleton"
				className="space-y-3"
			>
				<Skeleton className="h-8 w-48" />
				<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
					<Skeleton className="h-48" />
					<Skeleton className="h-48" />
					<Skeleton className="h-48" />
				</div>
			</div>
		);
	}

	const packs: PackItem[] = data?.data ?? [];

	if (packs.length === 0) {
		return (
			<div id="funding-packs">
				<p className="text-muted-foreground text-sm">
					No funding packs available.
				</p>
			</div>
		);
	}

	return (
		<div id="funding-packs">
			<h2 className="mb-4 text-xl font-semibold">Add Funds</h2>
			<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
				{packs.map((pack) => (
					<Card
						key={pack.id}
						data-testid={`pack-card-${pack.id}`}
						className={cn(
							"relative flex flex-col",
							pack.highlight_label && "border-primary border-2",
						)}
					>
						{pack.highlight_label && (
							<span
								data-testid={`highlight-badge-${pack.id}`}
								className="bg-primary text-primary-foreground absolute -top-3 left-4 rounded-full px-3 py-0.5 text-xs font-medium"
							>
								{pack.highlight_label}
							</span>
						)}
						<CardHeader>
							<CardTitle>{pack.name}</CardTitle>
							<CardDescription>{pack.description}</CardDescription>
						</CardHeader>
						<CardContent className="mt-auto space-y-4">
							<p className="text-2xl font-bold">{pack.price_display}</p>
							<Button
								className="w-full"
								disabled={checkoutPackId !== null}
								onClick={() => void handleAddFunds(pack.id)}
							>
								{checkoutPackId === pack.id ? (
									<>
										<Loader2 className="mr-2 h-4 w-4 animate-spin" />
										Redirecting…
									</>
								) : (
									"Add Funds"
								)}
							</Button>
						</CardContent>
					</Card>
				))}
			</div>
		</div>
	);
}
