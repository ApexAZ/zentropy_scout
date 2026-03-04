/**
 * Next.js proxy for auth-based routing and route protection.
 *
 * REQ-024 §5.2: Cookie-presence routing — authenticated users on public
 * routes (/, /login, /register) redirect to /dashboard. Unauthenticated
 * users on public routes see the landing page or auth forms.
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
const PATH_LOGIN = "/login";
const PATH_REGISTER = "/register";
const PATH_DASHBOARD = "/dashboard";

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
	const { pathname } = request.nextUrl;

	// --- Public routes (/, /login, /register) — REQ-024 §5.2 ---
	const isPublicRoute =
		pathname === "/" || pathname === PATH_LOGIN || pathname === PATH_REGISTER;

	if (isPublicRoute) {
		if (token) {
			return NextResponse.redirect(new URL(PATH_DASHBOARD, request.url));
		}
		return NextResponse.next();
	}

	// --- Protected routes — REQ-013 §8.6 ---
	if (!token) {
		return NextResponse.redirect(new URL(PATH_LOGIN, request.url));
	}

	// Admin route guard (REQ-022 §5.4)
	if (pathname.startsWith("/admin")) {
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
		 * Explicit public routes — proxy handles authenticated redirect
		 * to /dashboard (REQ-024 §5.2).
		 */
		"/login",
		"/register",
		/*
		 * Match all other request paths except:
		 * - /api (API routes handled by Next.js)
		 * - /_next (Next.js internals)
		 * - Static files by extension (served from /public, must bypass
		 *   auth because the Next.js Image optimizer fetches them
		 *   server-side without browser cookies)
		 *
		 * Note: / is matched here (empty string after leading slash
		 * passes all negative lookaheads). /login and /register are
		 * excluded by the regex but matched by explicit entries above.
		 */
		"/((?!login(?:/|$)|register(?:/|$)|api(?:/|$)|_next(?:/|$)|.*\\.(?:ico|png|svg|jpg|jpeg|gif|webp|txt|xml)$).*)", // NOSONAR — String.raw breaks Next.js static matcher analysis
	],
};
