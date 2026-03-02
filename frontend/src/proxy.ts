/**
 * Next.js proxy for auth route protection.
 *
 * REQ-013 §8.6: Server-side route protection — redirects unauthenticated
 * users to /login before any page renders.
 *
 * REQ-022 §5.4: Admin route guard — redirects non-admin users to /
 * for paths under /admin. Decodes JWT payload (base64, no verification)
 * to check the `adm` claim. This is a UX convenience only — the backend
 * `require_admin` dependency is the authoritative security check.
 */

import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE_NAME = "zentropy.session-token";

/**
 * Decode JWT payload without cryptographic verification.
 *
 * This is a UX-only check for fast admin route gating. The backend
 * validates the JWT fully — this just avoids loading the admin page
 * before the backend returns 403.
 */
function decodeJwtPayload(tokenValue: string): Record<string, unknown> | null {
	try {
		const parts = tokenValue.split(".");
		if (parts.length !== 3) return null;
		const payload = parts[1];
		const decoded = atob(payload.replaceAll("-", "+").replaceAll("_", "/"));
		return JSON.parse(decoded) as Record<string, unknown>;
	} catch {
		return null;
	}
}

export function proxy(request: NextRequest): NextResponse {
	const token = request.cookies.get(AUTH_COOKIE_NAME);

	if (!token) {
		return NextResponse.redirect(new URL("/login", request.url));
	}

	// Admin route guard (REQ-022 §5.4)
	if (request.nextUrl.pathname.startsWith("/admin")) {
		const payload = decodeJwtPayload(token.value);
		if (!payload?.adm) {
			return NextResponse.redirect(new URL("/", request.url));
		}
	}

	return NextResponse.next();
}

export const config = {
	matcher: [
		/*
		 * Match all request paths except:
		 * - /login, /register (auth pages — exact segment match)
		 * - /api (API routes handled by Next.js)
		 * - /_next (Next.js internals)
		 * - /favicon.ico, /robots.txt (static files)
		 */
		"/((?!login(?:/|$)|register(?:/|$)|api(?:/|$)|_next(?:/|$)|favicon\\.ico$|robots\\.txt$).*)", // NOSONAR — String.raw breaks Next.js static matcher analysis
	],
};
