/**
 * Next.js middleware for auth route protection.
 *
 * REQ-013 §8.6: Server-side route protection — redirects unauthenticated
 * users to /login before any page renders.
 *
 * This checks cookie PRESENCE only (not JWT validity). Full JWT validation
 * happens server-side in FastAPI's get_current_user_id(). This is a UX
 * optimization for fast redirects, not a security boundary.
 */

import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE_NAME = "zentropy.session-token";

export function middleware(request: NextRequest): NextResponse {
	const token = request.cookies.get(AUTH_COOKIE_NAME);

	if (!token) {
		return NextResponse.redirect(new URL("/login", request.url));
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
		"/((?!login(?:/|$)|register(?:/|$)|api(?:/|$)|_next(?:/|$)|favicon\\.ico$|robots\\.txt$).*)",
	],
};
