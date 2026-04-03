/**
 * @fileoverview Root layout for the Next.js application.
 *
 * Layer: layout
 * Feature: shared
 *
 * REQ-013: Wraps the entire app in the provider chain.
 * Provider order (outermost to innermost):
 * AuthProvider (REQ-013) > QueryProvider > SSEProvider > ChatProvider
 *
 * Coordinates with:
 * - lib/auth-provider.tsx: AuthProvider for session management
 * - lib/query-provider.tsx: QueryProvider for React Query
 * - lib/sse-provider.tsx: SSEProvider for server-sent events
 * - lib/chat-provider.tsx: ChatProvider for chat state
 * - components/ui/sonner.tsx: Toaster for toast notifications
 *
 * Called by / Used by:
 * - Next.js framework: root layout wrapping all routes
 */

import type { Metadata } from "next";
import { Nunito_Sans } from "next/font/google";

import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/lib/auth-provider";
import { ChatProvider } from "@/lib/chat-provider";
import { QueryProvider } from "@/lib/query-provider";
import { SSEProvider } from "@/lib/sse-provider";

import "./globals.css";

const nunitoSans = Nunito_Sans({
	weight: ["400", "500", "600", "700", "800", "900"],
	subsets: ["latin"],
	variable: "--font-nunito",
	display: "swap",
});

export const metadata: Metadata = {
	title: "Zentropy Scout",
	description: "AI-powered job application assistant",
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	return (
		<html
			lang="en"
			className={`dark ${nunitoSans.variable}`}
			suppressHydrationWarning
		>
			<body className="font-sans antialiased">
				<AuthProvider>
					<QueryProvider>
						<SSEProvider>
							<ChatProvider>{children}</ChatProvider>
						</SSEProvider>
					</QueryProvider>
				</AuthProvider>
				<Toaster />
			</body>
		</html>
	);
}
