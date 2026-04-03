/**
 * @fileoverview Zentropy wordmark logo component.
 *
 * Layer: component/ui
 * Feature: shared
 *
 * Renders "zen" in --color-logo-accent and "tropy" in foreground white.
 * Replaces the static zentropy_logo.png so the palette token controls
 * the accent color centrally.
 *
 * Coordinates with:
 * - app/globals.css: --color-logo-accent token
 * - components/layout/top-nav.tsx: nav wordmark
 * - app/login/page.tsx: login card wordmark
 * - app/(public)/components/landing-nav.tsx: landing nav wordmark
 */

import React from "react";

import { cn } from "@/lib/utils";

interface ZentropyLogoProps extends React.HTMLAttributes<HTMLSpanElement> {
	/** Tailwind classes applied to the outer element — use for sizing (text-2xl, text-3xl, etc.) */
	className?: string;
}

/**
 * Zentropy wordmark: "zen" in the logo accent color, "tropy" in foreground white.
 *
 * Args:
 *     className: Tailwind classes for sizing and spacing.
 *
 * Returns:
 *     Inline SVG wordmark that scales with font-size.
 */
export function ZentropyLogo({ className, ...props }: ZentropyLogoProps) {
	return (
		<span
			className={cn("select-none", className)}
			style={{
				fontFamily: "var(--font-nunito, var(--font-sans))",
				letterSpacing: "0.05em",
			}}
			aria-label="Zentropy"
			{...props}
		>
			<span
				style={{ color: "var(--color-logo-accent)", letterSpacing: "0.02em" }}
			>
				<span style={{ fontWeight: 800, fontSize: "1.05em" }}>z</span>
				<span style={{ fontWeight: 700 }}>en</span>
			</span>
			<span className="text-foreground">tropy</span>
		</span>
	);
}
