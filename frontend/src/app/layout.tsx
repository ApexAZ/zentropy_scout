import type { Metadata } from "next";

import { Toaster } from "@/components/ui/sonner";
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
				<QueryProvider>
					<SSEProvider>
						<ChatProvider>{children}</ChatProvider>
					</SSEProvider>
				</QueryProvider>
				<Toaster />
			</body>
		</html>
	);
}
