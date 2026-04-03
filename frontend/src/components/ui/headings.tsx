/**
 * @fileoverview Shared heading components for centralized typography control.
 *
 * Layer: component/ui
 * Feature: shared
 *
 * Three heading levels with standardized Tailwind classes. Importing pages
 * use these instead of writing raw h1/h2/h3 with class strings — one edit
 * here updates every heading across the app.
 *
 * Standard sizes:
 * - PageTitle (h1): text-2xl font-semibold tracking-tight
 * - SectionHeading (h2): text-lg font-semibold
 * - SubHeading (h3): text-base font-semibold
 *
 * Coordinates with:
 * - app/globals.css: --font-nunito token applied via body/heading base styles
 *
 * Called by / Used by:
 * - components/dashboard/dashboard-tabs.tsx: page title
 * - components/persona/persona-overview.tsx: page title, section headings, sub-headings
 * - components/resume/resume-list.tsx: page title
 * - components/resume/resume-detail.tsx: page title, section heading
 * - components/settings/settings-page.tsx: page title
 * - components/cover-letter/cover-letter-review.tsx: page title, sub-heading
 * - components/applications/application-detail.tsx: page title, section headings
 * - components/applications/applications-list.tsx: page title
 */

import React from "react";

import { cn } from "@/lib/utils";

/** Page-level title. Renders as h1 with text-2xl font-semibold tracking-tight. */
export function PageTitle({
	className,
	children,
	...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
	return (
		<h1
			className={cn("text-2xl font-semibold tracking-tight", className)}
			{...props}
		>
			{children}
		</h1>
	);
}

/** Major section heading within a page. Renders as h2 with text-lg font-semibold. */
export function SectionHeading({
	className,
	children,
	...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
	return (
		<h2 className={cn("text-lg font-semibold", className)} {...props}>
			{children}
		</h2>
	);
}

/** Sub-section heading within a card or panel. Renders as h3 with text-base font-semibold. */
export function SubHeading({
	className,
	children,
	...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
	return (
		<h3 className={cn("text-base font-semibold", className)} {...props}>
			{children}
		</h3>
	);
}
