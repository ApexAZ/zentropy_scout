/**
 * @fileoverview Client-side loader for the StarField component.
 *
 * Layer: component
 * Feature: shared
 *
 * Wraps StarField in next/dynamic with ssr:false so Math.random() star
 * positions are only generated on the client, avoiding hydration mismatch.
 * next/dynamic with ssr:false must be called from a Client Component.
 *
 * Coordinates with:
 * - app/(public)/components/star-field.tsx: the actual starfield component
 *
 * Called by / Used by:
 * - app/(public)/page.tsx: landing page background layer
 */

"use client";

import dynamic from "next/dynamic";

const StarField = dynamic(
	() => import("./star-field").then((m) => m.StarField),
	{ ssr: false },
);

export function StarFieldLoader() {
	return <StarField />;
}
