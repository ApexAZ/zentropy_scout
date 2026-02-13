"use client";

/**
 * Certification card for displaying a certification entry in the
 * onboarding wizard.
 *
 * REQ-012 §6.3.6: Each card shows certification_name,
 * issuing_organization, date_obtained, expiration_date (or
 * "Does not expire"), credential_id, verification_url with
 * edit/delete buttons.
 */

import { Pencil, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Certification } from "@/types/persona";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Defense-in-depth: only render clickable links for safe URL protocols. */
function isSafeUrl(url: string): boolean {
	try {
		const parsed = new URL(url);
		return parsed.protocol === "https:" || parsed.protocol === "http:";
	} catch {
		return false;
	}
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CertificationCardProps {
	entry: Certification;
	onEdit: (entry: Certification) => void;
	onDelete: (entry: Certification) => void;
	dragHandle: React.ReactNode | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CertificationCard({
	entry,
	onEdit,
	onDelete,
	dragHandle,
}: CertificationCardProps) {
	return (
		<div className="bg-card rounded-lg border">
			<div className="flex items-start gap-3 p-4">
				{dragHandle}
				<div className="min-w-0 flex-1">
					<div className="flex items-start justify-between gap-2">
						<div className="min-w-0">
							<h3 className="truncate font-medium">
								{entry.certification_name}
							</h3>
							<p className="text-muted-foreground text-sm">
								{entry.issuing_organization}
							</p>
						</div>
						<div className="flex shrink-0 gap-1">
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8"
								onClick={() => onEdit(entry)}
								aria-label={`Edit ${entry.certification_name}`}
							>
								<Pencil className="h-4 w-4" />
							</Button>
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8"
								onClick={() => onDelete(entry)}
								aria-label={`Delete ${entry.certification_name}`}
							>
								<Trash2 className="h-4 w-4" />
							</Button>
						</div>
					</div>
					<p className="text-muted-foreground mt-1 text-sm">
						{`Obtained ${entry.date_obtained}`}
						{entry.expiration_date
							? ` \u00B7 Expires ${entry.expiration_date}`
							: " \u00B7 Does not expire"}
					</p>
					{(entry.credential_id || entry.verification_url) && (
						<p className="text-muted-foreground mt-0.5 text-xs">
							{entry.credential_id && `ID: ${entry.credential_id}`}
							{entry.credential_id && entry.verification_url && " \u00B7 "}
							{entry.verification_url &&
								(isSafeUrl(entry.verification_url) ? (
									<a
										href={entry.verification_url}
										target="_blank"
										rel="noopener noreferrer"
										className="text-primary underline"
									>
										Verify
									</a>
								) : (
									<span className="text-muted-foreground">
										{entry.verification_url}
									</span>
								))}
						</p>
					)}
				</div>
			</div>
		</div>
	);
}
