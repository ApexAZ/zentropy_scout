/**
 * Root layout for the Next.js application.
 *
 * Provider order (outermost to innermost):
 * AuthProvider (REQ-013) > QueryProvider > SSEProvider > ChatProvider
 */

import type { Metadata } from "next";

import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/lib/auth-provider";
import { ChatProvider } from "@/lib/chat-provider";
import { QueryProvider } from "@/lib/query-provider";
import { SSEProvider } from "@/lib/sse-provider";

import "./globals.css";

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
		<html lang="en" suppressHydrationWarning>
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
