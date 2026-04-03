/**
 * @fileoverview Ambient starfield background effect for the landing page.
 *
 * Layer: component
 * Feature: shared
 *
 * Renders ~120 pinpoint dots that randomly fade in and out across the
 * full viewport. Colors drawn from the brand palette (amber, primary,
 * foreground). Stars are generated client-side only to avoid hydration
 * mismatch with random values.
 *
 * Coordinates with:
 * - app/globals.css: --color-logo-accent, --color-primary, --color-foreground tokens
 *
 * Called by / Used by:
 * - app/(public)/page.tsx: landing page background layer
 */

"use client";

import { useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Star {
	id: number;
	x: number;
	y: number;
	size: number;
	color: string;
	duration: number;
	delay: number;
	peakOpacity: number;
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const BASE_STAR_COUNT = 700;
const BASE_AREA = 3840 * 2160;

function getStarCount(): number {
	if (typeof window === "undefined") return 0;
	const area = window.innerWidth * window.innerHeight;
	return Math.max(80, Math.round((area / BASE_AREA) * BASE_STAR_COUNT));
}

const COLORS = [
	"var(--color-logo-accent)",
	"var(--color-logo-accent)",
	"var(--color-primary)",
	"var(--color-foreground)",
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StarField() {
	const [stars] = useState<Star[]>(() =>
		Array.from({ length: getStarCount() }, (_, i) => ({
			id: i,
			x: Math.random() * 100,
			y: Math.random() * 100,
			size: Math.random() < 0.6 ? 1 : 3,
			color: COLORS[Math.floor(Math.random() * COLORS.length)],
			duration: Math.random() * 5 + 6,
			delay: Math.random() * 10,
			peakOpacity: Math.random() * 0.45 + 0.27,
		})),
	);

	return (
		<>
			<style>{`
				@keyframes star-pulse {
					0%, 100% { opacity: 0; }
					50% { opacity: 1; }
				}
			`}</style>
			<div
				className="pointer-events-none fixed inset-0 overflow-hidden"
				aria-hidden="true"
			>
				{stars.map((star) => (
					<div
						key={star.id}
						className="absolute"
						style={{
							left: `${star.x}%`,
							top: `${star.y}%`,
							opacity: star.peakOpacity,
						}}
					>
						<div
							className="rounded-full"
							style={{
								width: `${star.size}px`,
								height: `${star.size}px`,
								backgroundColor: star.color,
								animation: `star-pulse ${star.duration}s ease-in-out ${star.delay}s infinite`,
							}}
						/>
					</div>
				))}
			</div>
		</>
	);
}
