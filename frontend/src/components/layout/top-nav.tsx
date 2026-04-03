"use client";

/**
 * @fileoverview Top navigation bar with links, badges, balance, and chat toggle.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-012 §3.2: Horizontal top bar with links to major sections,
 * chat toggle button, and critical info badge indicators.
 * REQ-020 §9.1: Balance indicator with color coding.
 *
 * Coordinates with:
 * - hooks/use-balance.ts: account balance fetch for balance indicator
 * - lib/auth-provider.tsx: useSession for admin check
 * - lib/chat-panel-provider.tsx: useChatPanel for chat toggle
 * - lib/format-utils.ts: formatBalance, getBalanceColorClass
 * - lib/utils.ts: cn class name helper
 *
 * Called by / Used by:
 * - components/layout/app-shell.tsx: rendered as top nav in app shell
 */

import {
	Briefcase,
	FileText,
	LayoutDashboard,
	MessageSquare,
	Settings,
	Shield,
	User,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType } from "react";

import { useBalance } from "@/hooks/use-balance";
import { useSession } from "@/lib/auth-provider";
import { useChatPanel } from "@/lib/chat-panel-provider";
import { formatBalance, getBalanceColorClass } from "@/lib/format-utils";
import { cn } from "@/lib/utils";
import { ZentropyLogo } from "@/components/ui/zentropy-logo";

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
	{
		href: "/applications",
		label: "Applications",
		icon: Briefcase,
		badgeTestId: "active-applications-badge",
	},
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
	{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isActive(pathname: string, href: string): boolean {
	return pathname.startsWith(href);
}

function navLinkClasses(active: boolean, extra?: string): string {
	return cn(
		"flex items-center gap-2 px-3 py-2 text-sm font-medium transition-colors",
		active
			? "text-primary self-stretch"
			: "rounded-md text-muted-foreground hover:bg-secondary/50 hover:text-foreground",
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
	const { session } = useSession();
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
	const adminActive = isActive(pathname, "/admin");

	return (
		<header className="bg-background border-b">
			<nav aria-label="Main navigation" className="flex h-16 items-center px-6">
				{/* Brand */}
				<Link
					href="/dashboard"
					className="mr-6 flex items-center"
					aria-label="Zentropy Scout home"
				>
					<ZentropyLogo className="text-4xl" />
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
								<span className="relative flex translate-y-[2px] items-center gap-2">
									<Icon className="h-4 w-4" />
									{label}
									{active && (
										<span className="bg-primary absolute right-0 bottom-[-4px] left-0 h-[2px]" />
									)}
								</span>
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

				{/* Right side: Balance + Admin + Settings + Chat toggle */}
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

					{session?.isAdmin && (
						<Link
							href="/admin/config"
							aria-current={adminActive ? "page" : undefined}
							className={navLinkClasses(adminActive, "hidden md:flex")}
						>
							<Shield className="h-4 w-4" />
							Admin
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
