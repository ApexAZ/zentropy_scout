/**
 * @fileoverview URL validation utilities for safe link rendering.
 *
 * Layer: lib/utility
 * Feature: shared
 *
 * REQ-012 §8.2, §9.1: Prevents XSS via javascript:, data:, or other
 * dangerous URL schemes. Only allows http: and https: protocols.
 * Used wherever external URLs from job postings or personas are rendered.
 *
 * Coordinates with:
 * - (no upstream lib imports — pure validation utility)
 *
 * Called by / Used by:
 * - components/editor/editor-toolbar.tsx: safe link insertion in rich text editor
 * - components/editor/resume-editor.tsx: link validation in resume content
 * - components/jobs/job-detail-header.tsx: external job posting links
 * - components/jobs/mark-as-applied-card.tsx: application URL validation
 * - components/applications/job-snapshot-section.tsx: snapshot link display
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SAFE_PROTOCOLS = new Set(["https:", "http:"]);

// ---------------------------------------------------------------------------
// Functions
// ---------------------------------------------------------------------------

/** Returns true if the URL uses a safe protocol (http or https). */
export function isSafeUrl(url: string): boolean {
	try {
		return SAFE_PROTOCOLS.has(new URL(url).protocol);
	} catch {
		return false;
	}
}

/** Extracts hostname from a URL, stripping "www." prefix. Returns raw string on parse failure. */
export function getHostname(url: string): string {
	try {
		return new URL(url).hostname.replace(/^www\./, "");
	} catch {
		return url;
	}
}
