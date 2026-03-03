/**
 * Public route group layout — minimal wrapper without app shell.
 *
 * REQ-024 §5.1: Landing page uses a separate layout without
 * sidebar or app navigation.
 */

export default function PublicLayout({
	children,
}: Readonly<{ children: React.ReactNode }>) {
	return <main className="bg-background min-h-screen">{children}</main>;
}
