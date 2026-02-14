/**
 * URL validation utilities for safe link rendering.
 *
 * Prevents XSS via javascript:, data:, or other dangerous URL schemes.
 * Only allows http: and https: protocols.
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
