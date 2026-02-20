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
	useContext,
	useEffect,
	useMemo,
	useState,
	type ReactNode,
} from "react";

import { apiGet } from "@/lib/api-client";

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
}

interface SessionContext {
	session: User | null;
	status: AuthStatus;
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

	const contextValue = useMemo(() => ({ session, status }), [session, status]);

	return <AuthContext value={contextValue}>{children}</AuthContext>;
}
