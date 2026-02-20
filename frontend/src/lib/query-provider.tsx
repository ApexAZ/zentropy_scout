"use client";

/**
 * TanStack Query provider for the Next.js App Router.
 *
 * REQ-012 §4.2.1: QueryClientProvider wraps the application tree.
 * Must be a client component ("use client") because QueryClientProvider
 * uses React context.
 *
 * ReactQueryDevtools renders as a no-op in production (guarded internally
 * by the library via process.env.NODE_ENV check and tree-shaken by the bundler).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useEffect, useState, type ReactNode } from "react";

import { createQueryClient, setActiveQueryClient } from "./query-client";

interface QueryProviderProps {
	children: ReactNode;
	/** Optional pre-configured client (useful for testing). */
	client?: QueryClient;
}

export function QueryProvider({
	children,
	client,
}: Readonly<QueryProviderProps>) {
	// Create the QueryClient once per component lifecycle to avoid
	// re-creating on every render in React strict mode.
	const [queryClient] = useState(() => client ?? createQueryClient());

	// Expose the active client for non-React code (e.g., api-client 401 interceptor).
	useEffect(() => {
		setActiveQueryClient(queryClient);
		return () => setActiveQueryClient(null);
	}, [queryClient]);

	return (
		<QueryClientProvider client={queryClient}>
			{children}
			<ReactQueryDevtools initialIsOpen={false} />
		</QueryClientProvider>
	);
}
