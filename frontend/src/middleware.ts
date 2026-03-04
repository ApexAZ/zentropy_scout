/**
 * Next.js middleware for auth-based routing.
 *
 * REQ-024 §5.2: Cookie-presence check routes users between the public
 * landing page and the authenticated dashboard.
 *
 * Cookie detection is presence-only — no JWT validation. Full JWT
 * validation happens client-side in AuthProvider. If the cookie exists
 * but is expired/invalid, AuthProvider catches it and redirects to /login.
 */

import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE_NAME = "zentropy.session-token";
const PATH_DASHBOARD = "/dashboard";
const PATH_LOGIN = "/login";
const PATH_REGISTER = "/register";

export function middleware(request: NextRequest): NextResponse {
	const hasSession = request.cookies.has(AUTH_COOKIE_NAME);
	const { pathname } = request.nextUrl;

	// GET / + cookie → redirect to /dashboard
	if (pathname === "/" && hasSession) {
		return NextResponse.redirect(new URL(PATH_DASHBOARD, request.url));
	}

	// GET /dashboard + no cookie → redirect to /login
	if (pathname === PATH_DASHBOARD && !hasSession) {
		return NextResponse.redirect(new URL(PATH_LOGIN, request.url));
	}

	// GET /login or /register + cookie → redirect to /dashboard
	if ((pathname === PATH_LOGIN || pathname === PATH_REGISTER) && hasSession) {
		return NextResponse.redirect(new URL(PATH_DASHBOARD, request.url));
	}

	// All other matched routes → pass through
	return NextResponse.next();
}

export const config = {
	matcher: ["/", PATH_DASHBOARD, PATH_LOGIN, PATH_REGISTER],
};
