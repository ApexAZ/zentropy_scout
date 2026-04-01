/**
 * @fileoverview Public route group layout — minimal wrapper without app shell.
 *
 * Layer: layout
 * Feature: shared
 *
 * REQ-024 §5.1: Landing page uses a separate layout without
 * sidebar or app navigation.
 *
 * Coordinates with:
 * - (no upstream lib imports — pure wrapper layout)
 *
 * Called by / Used by:
 * - Next.js framework: layout for the (public) route group (landing page)
 */

export default function PublicLayout({
	children,
}: Readonly<{ children: React.ReactNode }>) {
	return <main className="bg-background min-h-screen">{children}</main>;
}
