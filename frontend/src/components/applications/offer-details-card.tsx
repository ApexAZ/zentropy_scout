"use client";

/**
 * Read-only card displaying captured offer details with deadline countdown.
 *
 * REQ-012 §11.5: Offer details display with response deadline countdown.
 * Shown on application detail page when status is Offer or Accepted.
 */

import { Pencil } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { OfferDetails } from "@/types/application";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LABEL_CLASS = "text-muted-foreground text-sm";
const VALUE_CLASS = "text-sm font-medium";
const VALID_CURRENCIES: ReadonlySet<string> = new Set([
	"USD",
	"EUR",
	"GBP",
	"CAD",
	"AUD",
	"CHF",
	"JPY",
]);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface OfferDetailsCardProps {
	offerDetails: OfferDetails;
	onEdit: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(amount: number, currency: string): string {
	const safeCurrency = VALID_CURRENCIES.has(currency) ? currency : "USD";
	return new Intl.NumberFormat("en-US", {
		style: "currency",
		currency: safeCurrency,
		maximumFractionDigits: 0,
	}).format(amount);
}

function formatDate(dateString: string): string {
	const date = new Date(dateString + "T00:00:00Z");
	if (Number.isNaN(date.getTime())) return "Unknown";
	return date.toLocaleDateString("en-US", {
		month: "short",
		day: "numeric",
		year: "numeric",
		timeZone: "UTC",
	});
}

function formatDeadlineCountdown(dateString: string): string {
	const deadline = new Date(dateString + "T00:00:00Z");
	if (Number.isNaN(deadline.getTime())) return "Unknown";
	const today = new Date();
	today.setUTCHours(0, 0, 0, 0);

	const diffMs = deadline.getTime() - today.getTime();
	const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

	if (diffDays < 0) return "Expired";
	if (diffDays === 0) return "Today";
	if (diffDays === 1) return "1 day remaining";
	return `${diffDays} days remaining`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function OfferDetailsCard({
	offerDetails,
	onEdit,
}: Readonly<OfferDetailsCardProps>) {
	const {
		base_salary,
		salary_currency,
		bonus_percent,
		equity_value,
		equity_type,
		equity_vesting_years,
		start_date,
		response_deadline,
		other_benefits,
		notes,
	} = offerDetails;

	const hasSalary = base_salary !== undefined;
	const hasBonus = bonus_percent !== undefined;
	const hasEquity = equity_value !== undefined;
	const hasStartDate = start_date !== undefined;
	const hasDeadline = response_deadline !== undefined;
	const hasBenefits = other_benefits !== undefined && other_benefits !== "";
	const hasNotes = notes !== undefined && notes !== "";

	return (
		<Card data-testid="offer-details-card">
			<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
				<CardTitle className="text-base">Offer Details</CardTitle>
				<Button variant="ghost" size="sm" onClick={onEdit} className="gap-1">
					<Pencil className="h-3.5 w-3.5" />
					Edit
				</Button>
			</CardHeader>
			<CardContent className="space-y-3">
				{hasSalary && (
					<div data-testid="offer-salary-row">
						<p className={LABEL_CLASS}>Base Salary</p>
						<p className={VALUE_CLASS}>
							{formatCurrency(base_salary, salary_currency ?? "USD")}
						</p>
					</div>
				)}

				{hasBonus && (
					<div data-testid="offer-bonus-row">
						<p className={LABEL_CLASS}>Bonus</p>
						<p className={VALUE_CLASS}>{bonus_percent}%</p>
					</div>
				)}

				{hasEquity && (
					<div data-testid="offer-equity-row">
						<p className={LABEL_CLASS}>Equity</p>
						<p className={VALUE_CLASS}>
							{formatCurrency(equity_value, salary_currency ?? "USD")}
							{equity_type && ` ${equity_type}`}
							{equity_vesting_years !== undefined &&
								`, ${equity_vesting_years}-year vest`}
						</p>
					</div>
				)}

				{hasStartDate && (
					<div data-testid="offer-start-date-row">
						<p className={LABEL_CLASS}>Start Date</p>
						<p className={VALUE_CLASS}>{formatDate(start_date)}</p>
					</div>
				)}

				{hasDeadline && (
					<div data-testid="offer-deadline-row">
						<p className={LABEL_CLASS}>Deadline</p>
						<p className={VALUE_CLASS}>
							{formatDate(response_deadline)} (
							{formatDeadlineCountdown(response_deadline)})
						</p>
					</div>
				)}

				{hasBenefits && (
					<div data-testid="offer-benefits-row">
						<p className={LABEL_CLASS}>Benefits</p>
						<p className={VALUE_CLASS}>{other_benefits}</p>
					</div>
				)}

				{hasNotes && (
					<div data-testid="offer-notes-row">
						<p className={LABEL_CLASS}>Notes</p>
						<p className={VALUE_CLASS}>{notes}</p>
					</div>
				)}
			</CardContent>
		</Card>
	);
}
