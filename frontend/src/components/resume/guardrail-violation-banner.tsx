"use client";

/**
 * @fileoverview Guardrail violation banner for variant review.
 *
 * Layer: component
 * Feature: resume
 *
 * REQ-012 §9.4: Shows guardrail violations with severity indicators
 * and a link to fix persona data.
 *
 * Coordinates with:
 * - types/resume.ts: GuardrailViolation type
 *
 * Called by / Used by:
 * - components/resume/variant-review.tsx: displayed when variant has guardrail violations
 */

import { AlertTriangle } from "lucide-react";
import Link from "next/link";

import type { GuardrailViolation } from "@/types/resume";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GuardrailViolationBanner({
	violations,
}: Readonly<{
	violations: GuardrailViolation[];
}>) {
	return (
		<div
			data-testid="guardrail-violations"
			role="alert"
			className="border-destructive/20 bg-destructive/10 mt-4 rounded-lg border p-4"
		>
			<div className="mb-2 flex items-center gap-2">
				<AlertTriangle className="text-destructive h-4 w-4" />
				<span className="text-destructive text-sm font-semibold">
					Guardrail Violation
				</span>
			</div>
			<ul className="text-destructive mb-3 list-disc space-y-1 pl-5 text-sm">
				{violations.map((v) => (
					<li key={v.rule}>{v.message}</li>
				))}
			</ul>
			<div className="flex items-center gap-2">
				<Link
					href="/persona"
					data-testid="go-to-persona-link"
					className="text-destructive hover:text-destructive/80 text-sm font-medium underline"
				>
					Go to Persona
				</Link>
			</div>
		</div>
	);
}
