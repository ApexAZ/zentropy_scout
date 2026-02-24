"use client";

/**
 * AuthProvider — session context for the frontend.
 *
 * REQ-013 §8.4–§8.5: On mount, calls GET /api/v1/auth/me to validate
 * the JWT cookie. Provides session state via useSession() hook.
 * Revalidates on tab focus (visibility change) for defense-in-depth.
 *
 * Status lifecycle: "loading" → "authenticated" | "unauthenticated"
 */

import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useMemo,
	useState,
	type ReactNode,
} from "react";

import { apiGet, apiPost } from "@/lib/api-client";
import { getActiveQueryClient } from "@/lib/query-client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface User {
	id: string;
	email: string;
	name: string | null;
	image: string | null;
	emailVerified: boolean;
	hasPassword: boolean;
	canResetPassword: boolean;
}

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

/** Raw shape from GET /auth/me (snake_case from backend). */
interface MeResponse {
	id: string;
	email: string;
	name: string | null;
	image: string | null;
	email_verified: boolean;
	has_password: boolean;
	can_reset_password?: boolean;
}

interface SessionContext {
	session: User | null;
	status: AuthStatus;
	/** Sign out the current device (REQ-013 §8.9). */
	logout: () => Promise<void>;
	/** Invalidate all sessions then sign out (REQ-013 §8.9). */
	logoutAllDevices: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<SessionContext | null>(null);

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Access the current session state.
 *
 * Must be used within an AuthProvider. Throws if used outside.
 */
export function useSession(): SessionContext {
	const ctx = useContext(AuthContext);
	if (ctx === null) {
		throw new Error("useSession must be used within an AuthProvider");
	}
	return ctx;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface AuthProviderProps {
	children: ReactNode;
}

export function AuthProvider({ children }: Readonly<AuthProviderProps>) {
	const [session, setSession] = useState<User | null>(null);
	const [status, setStatus] = useState<AuthStatus>("loading");

	useEffect(() => {
		let cancelled = false;

		async function checkSession() {
			try {
				const response = await apiGet<{ data: MeResponse }>("/auth/me");
				if (!cancelled) {
					const me = response.data;
					setSession({
						id: me.id,
						email: me.email,
						name: me.name,
						image: me.image,
						emailVerified: me.email_verified,
						hasPassword: me.has_password,
						canResetPassword: me.can_reset_password ?? false,
					});
					setStatus("authenticated");
				}
			} catch {
				if (!cancelled) {
					setSession(null);
					setStatus("unauthenticated");
				}
			}
		}

		checkSession();

		function handleVisibilityChange() {
			if (document.visibilityState === "visible") {
				checkSession();
			}
		}

		document.addEventListener("visibilitychange", handleVisibilityChange);

		return () => {
			cancelled = true;
			document.removeEventListener("visibilitychange", handleVisibilityChange);
		};
	}, []);

	/**
	 * Sign out the current device (REQ-013 §8.9).
	 *
	 * 1. POST /auth/logout (clears httpOnly cookie server-side)
	 * 2. Clear TanStack Query cache
	 * 3. Clear AuthProvider context
	 * 4. Redirect to /login
	 *
	 * Always redirects even if the API call fails — the cookie may
	 * already be invalid, so staying on an authenticated page is wrong.
	 */
	const logout = useCallback(async () => {
		try {
			await apiPost("/auth/logout");
		} catch {
			// Swallow — cookie may already be invalid or network down.
			// Proceed with local cleanup regardless.
		}
		const qc = getActiveQueryClient();
		if (qc) qc.clear();
		setSession(null);
		setStatus("unauthenticated");
		globalThis.location.href = "/login";
	}, []);

	/**
	 * Invalidate all sessions then sign out (REQ-013 §8.9).
	 *
	 * Sets token_invalidated_before = now() on the server, making all
	 * other devices' JWTs invalid on their next API call. Then executes
	 * the normal logout flow for this device.
	 */
	const logoutAllDevices = useCallback(async () => {
		try {
			await apiPost("/auth/invalidate-sessions");
		} catch {
			// Swallow — proceed with local logout regardless.
		}
		await logout();
	}, [logout]);

	const contextValue = useMemo(
		() => ({ session, status, logout, logoutAllDevices }),
		[session, status, logout, logoutAllDevices],
	);

	return <AuthContext value={contextValue}>{children}</AuthContext>;
}
