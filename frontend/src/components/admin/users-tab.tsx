"use client";

/**
 * User admin management tab.
 *
 * REQ-022 §11.2, §10.6: User list with admin toggle, env-protected badge,
 * balance display, and pagination.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Loader2, Shield } from "lucide-react";

import { fetchUsers, toggleAdmin } from "@/lib/api/admin";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** User administration — list with admin toggle and pagination. */
export function UsersTab() {
	const queryClient = useQueryClient();
	const [page, setPage] = useState(1);

	// -----------------------------------------------------------------------
	// Queries
	// -----------------------------------------------------------------------

	const { data, isLoading, error, refetch } = useQuery({
		queryKey: [...queryKeys.adminUsers, page],
		queryFn: () => fetchUsers({ page, per_page: 50 }),
	});

	// -----------------------------------------------------------------------
	// Mutations
	// -----------------------------------------------------------------------

	const toggleMut = useMutation({
		mutationFn: ({ id, isAdmin }: { id: string; isAdmin: boolean }) =>
			toggleAdmin(id, isAdmin),
		onSuccess: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.adminUsers,
			});
			showToast.success("User updated");
		},
		onError: () => {
			showToast.error("Failed to update user");
		},
	});

	// -----------------------------------------------------------------------
	// Loading / Error
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div data-testid="users-loading" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (error) {
		return (
			<div className="py-8 text-center">
				<p className="text-destructive mb-2">Failed to load users.</p>
				<Button variant="outline" size="sm" onClick={() => void refetch()}>
					Retry
				</Button>
			</div>
		);
	}

	const items = data?.data ?? [];
	const meta = data?.meta;
	const totalPages = meta?.total_pages ?? 1;
	const total = meta?.total ?? items.length;

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="users-tab" className="space-y-4 pt-4">
			<p className="text-muted-foreground text-sm">
				{total} user{total === 1 ? "" : "s"}
			</p>

			{items.length === 0 ? (
				<p className="text-muted-foreground py-8 text-center text-sm">
					No users found.
				</p>
			) : (
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead>Email</TableHead>
							<TableHead>Name</TableHead>
							<TableHead>Role</TableHead>
							<TableHead>Balance</TableHead>
							<TableHead className="text-right">Actions</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{items.map((item) => (
							<TableRow key={item.id}>
								<TableCell className="font-mono text-xs">
									{item.email}
								</TableCell>
								<TableCell>{item.name ?? "—"}</TableCell>
								<TableCell>
									<div className="flex items-center gap-2">
										{item.is_admin ? (
											<span className="flex items-center gap-1 text-sm font-medium">
												<Shield className="h-3.5 w-3.5" />
												Admin
											</span>
										) : (
											<span className="text-muted-foreground text-sm">
												User
											</span>
										)}
										{item.is_env_protected && (
											<span className="rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-200">
												Protected
											</span>
										)}
									</div>
								</TableCell>
								<TableCell>${item.balance_usd}</TableCell>
								<TableCell className="text-right">
									{item.is_admin ? (
										<Button
											variant="ghost"
											size="sm"
											aria-label="Remove admin"
											disabled={item.is_env_protected}
											onClick={() =>
												toggleMut.mutate({
													id: item.id,
													isAdmin: false,
												})
											}
										>
											Remove Admin
										</Button>
									) : (
										<Button
											variant="ghost"
											size="sm"
											aria-label="Make admin"
											onClick={() =>
												toggleMut.mutate({
													id: item.id,
													isAdmin: true,
												})
											}
										>
											Make Admin
										</Button>
									)}
								</TableCell>
							</TableRow>
						))}
					</TableBody>
				</Table>
			)}

			{/* Pagination */}
			{totalPages > 1 && (
				<div className="flex items-center justify-center gap-2 pt-2">
					<Button
						variant="outline"
						size="sm"
						aria-label="Previous page"
						disabled={page <= 1}
						onClick={() => setPage((p) => p - 1)}
					>
						<ChevronLeft className="h-4 w-4" />
						Previous
					</Button>
					<span className="text-muted-foreground text-sm">
						Page {page} of {totalPages}
					</span>
					<Button
						variant="outline"
						size="sm"
						aria-label="Next page"
						disabled={page >= totalPages}
						onClick={() => setPage((p) => p + 1)}
					>
						Next
						<ChevronRight className="ml-1 h-4 w-4" />
					</Button>
				</div>
			)}
		</div>
	);
}
