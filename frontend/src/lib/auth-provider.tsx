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

interface User {
	id: string;
	email: string;
	name: string | null;
	image: string | null;
}

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

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

export function AuthProvider({ children }: AuthProviderProps) {
	const [session, setSession] = useState<User | null>(null);
	const [status, setStatus] = useState<AuthStatus>("loading");

	useEffect(() => {
		let cancelled = false;

		async function checkSession() {
			try {
				const response = await apiGet<{ data: User }>("/auth/me");
				if (!cancelled) {
					setSession(response.data);
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
