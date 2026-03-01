"use client";

/**
 * Top navigation bar.
 *
 * REQ-012 §3.2: Horizontal top bar with links to major sections,
 * chat toggle button, and critical info badge indicators.
 * REQ-020 §9.1: Balance indicator with color coding.
 */

import {
	Briefcase,
	FileText,
	LayoutDashboard,
	MessageSquare,
	Settings,
	User,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType } from "react";

import { useBalance } from "@/hooks/use-balance";
import { useChatPanel } from "@/lib/chat-panel-provider";
import { formatBalance, getBalanceColorClass } from "@/lib/format-utils";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TopNavProps {
	/** Number of pending persona change flags. */
	pendingFlagsCount?: number;
	/** Number of materials awaiting user review/approval. */
	pendingReviewsCount?: number;
	/** Number of active job applications. */
	activeApplicationsCount?: number;
}

// ---------------------------------------------------------------------------
// Nav configuration
// ---------------------------------------------------------------------------

interface NavItem {
	href: string;
	label: string;
	icon: ComponentType<{ className?: string }>;
	badgeTestId?: string;
}

const PRIMARY_NAV_ITEMS: NavItem[] = [
	{ href: "/", label: "Dashboard", icon: LayoutDashboard },
	{
		href: "/persona",
		label: "Persona",
		icon: User,
		badgeTestId: "pending-flags-badge",
	},
	{
		href: "/resumes",
		label: "Resumes",
		icon: FileText,
		badgeTestId: "pending-reviews-badge",
	},
	{
		href: "/applications",
		label: "Applications",
		icon: Briefcase,
		badgeTestId: "active-applications-badge",
	},
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isActive(pathname: string, href: string): boolean {
	if (href === "/") return pathname === "/";
	return pathname.startsWith(href);
}

function navLinkClasses(active: boolean, extra?: string): string {
	return cn(
		"flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
		active
			? "bg-secondary text-foreground"
			: "text-muted-foreground hover:bg-secondary/50 hover:text-foreground",
		extra,
	);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TopNav({
	pendingFlagsCount = 0,
	pendingReviewsCount = 0,
	activeApplicationsCount = 0,
}: Readonly<TopNavProps>) {
	const pathname = usePathname();
	const { toggle } = useChatPanel();
	const {
		balance,
		isLoading: balanceLoading,
		error: balanceError,
	} = useBalance();

	const badgeCounts: Record<string, number> = {
		"pending-flags-badge": pendingFlagsCount,
		"pending-reviews-badge": pendingReviewsCount,
		"active-applications-badge": activeApplicationsCount,
	};

	const settingsActive = isActive(pathname, "/settings");

	return (
		<header className="bg-background border-b">
			<nav aria-label="Main navigation" className="flex h-14 items-center px-4">
				{/* Brand */}
				<Link
					href="/"
					className="mr-6 text-lg font-semibold"
					aria-label="Zentropy Scout home"
				>
					Zentropy Scout
				</Link>

				{/* Primary nav links */}
				<div className="hidden items-center gap-1 md:flex">
					{PRIMARY_NAV_ITEMS.map(({ href, label, icon: Icon, badgeTestId }) => {
						const active = isActive(pathname, href);
						const badgeCount = badgeTestId ? badgeCounts[badgeTestId] : 0;

						return (
							<Link
								key={href}
								href={href}
								aria-current={active ? "page" : undefined}
								className={navLinkClasses(active)}
							>
								<Icon className="h-4 w-4" />
								{label}
								{badgeCount > 0 && (
									<span
										data-testid={badgeTestId}
										className="bg-primary text-primary-foreground inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-xs font-medium"
									>
										{badgeCount}
									</span>
								)}
							</Link>
						);
					})}
				</div>

				{/* Right side: Balance + Settings + Chat toggle */}
				<div className="ml-auto flex items-center gap-2">
					{balance !== undefined && !balanceLoading && !balanceError && (
						<Link href="/usage" className="hidden md:flex">
							<span
								data-testid="balance-indicator"
								className={cn(
									"text-sm font-medium",
									getBalanceColorClass(Number.parseFloat(balance)),
								)}
							>
								{formatBalance(balance)}
							</span>
						</Link>
					)}

					<Link
						href="/settings"
						aria-current={settingsActive ? "page" : undefined}
						className={navLinkClasses(settingsActive, "hidden md:flex")}
					>
						<Settings className="h-4 w-4" />
						Settings
					</Link>

					<button
						type="button"
						onClick={toggle}
						aria-label="Toggle chat"
						className="text-muted-foreground hover:bg-secondary/50 hover:text-foreground rounded-md p-2 transition-colors"
					>
						<MessageSquare className="h-5 w-5" />
					</button>
				</div>
			</nav>
		</header>
	);
}
