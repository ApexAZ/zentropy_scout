import type { Metadata } from "next";
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
			<body className="font-sans antialiased">{children}</body>
		</html>
	);
}
