/**
 * Account settings section — displayed at the top of the Settings page.
 *
 * REQ-013 §8.3a: Email display + verified badge, name edit,
 * password change/set, sign out, sign out all devices.
 */

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, apiPatch, apiPost } from "@/lib/api-client";
import { useSession } from "@/lib/auth-provider";
import { showToast } from "@/lib/toast";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function VerifiedBadge({ verified }: Readonly<{ verified: boolean }>) {
	return verified ? (
		<span className="text-xs font-medium text-green-600">Verified</span>
	) : (
		<span className="text-destructive text-xs font-medium">Unverified</span>
	);
}

// ---------------------------------------------------------------------------
// Standalone handlers (no component state dependency)
// ---------------------------------------------------------------------------

async function handleSignOut() {
	try {
		await apiPost("/auth/logout");
	} finally {
		globalThis.location.href = "/login";
	}
}

async function handleSignOutAllDevices() {
	try {
		await apiPost("/auth/invalidate-sessions");
		await apiPost("/auth/logout");
	} finally {
		globalThis.location.href = "/login";
	}
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AccountSection() {
	const { session } = useSession();

	// Name editing state
	const [editingName, setEditingName] = useState(false);
	const [nameValue, setNameValue] = useState(session?.name ?? "");
	const [displayName, setDisplayName] = useState(session?.name ?? "");

	// Password form state
	const [showPasswordForm, setShowPasswordForm] = useState(false);
	const [currentPassword, setCurrentPassword] = useState("");
	const [newPassword, setNewPassword] = useState("");
	const [confirmNewPassword, setConfirmNewPassword] = useState("");
	const [passwordError, setPasswordError] = useState<string | null>(null);
	const [passwordSubmitting, setPasswordSubmitting] = useState(false);

	// Sign out all devices confirmation
	const [showSignOutAllConfirm, setShowSignOutAllConfirm] = useState(false);

	if (!session) return null;

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	function handleEditName() {
		setNameValue(displayName);
		setEditingName(true);
	}

	function handleCancelName() {
		setEditingName(false);
	}

	async function handleSaveName() {
		try {
			await apiPatch("/auth/profile", { name: nameValue });
			setDisplayName(nameValue);
			setEditingName(false);
			showToast.success("Name updated");
		} catch {
			showToast.error("Failed to update name");
		}
	}

	function handleOpenPasswordForm() {
		setCurrentPassword("");
		setNewPassword("");
		setConfirmNewPassword("");
		setPasswordError(null);
		setShowPasswordForm(true);
	}

	async function handlePasswordSubmit() {
		if (!session) return;

		// Client-side validation
		if (newPassword !== confirmNewPassword) {
			setPasswordError("Passwords do not match");
			return;
		}

		setPasswordError(null);
		setPasswordSubmitting(true);
		try {
			await apiPost("/auth/change-password", {
				current_password: session.hasPassword ? currentPassword : null,
				new_password: newPassword,
			});
			setShowPasswordForm(false);
			showToast.success("Password updated");
		} catch (err) {
			if (err instanceof ApiError && err.status === 401) {
				setPasswordError("Current password is incorrect");
			} else if (err instanceof ApiError && err.code === "PASSWORD_BREACHED") {
				setPasswordError(
					"This password has appeared in a data breach. Please choose a different one.",
				);
			} else if (err instanceof ApiError && err.status === 400) {
				setPasswordError(
					"Password does not meet requirements. Please try a stronger password.",
				);
			} else {
				setPasswordError("Failed to update password. Please try again.");
			}
		} finally {
			setPasswordSubmitting(false);
		}
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="account-section" className="space-y-6">
			{/* Email */}
			<div className="flex items-center gap-2">
				<span className="text-muted-foreground text-sm">Email:</span>
				<span className="text-sm font-medium">{session.email}</span>
				<VerifiedBadge verified={session.emailVerified} />
			</div>

			{/* Name */}
			<div>
				{editingName ? (
					<div className="space-y-2">
						<Label htmlFor="account-name">Name</Label>
						<Input
							id="account-name"
							value={nameValue}
							onChange={(e) => setNameValue(e.target.value)}
							maxLength={255}
						/>
						<div className="flex gap-2">
							<Button size="sm" onClick={handleSaveName}>
								Save
							</Button>
							<Button size="sm" variant="outline" onClick={handleCancelName}>
								Cancel
							</Button>
						</div>
					</div>
				) : (
					<div className="flex items-center gap-2">
						<span className="text-muted-foreground text-sm">Name:</span>
						<span className="text-sm font-medium">{displayName}</span>
						<Button
							size="sm"
							variant="ghost"
							onClick={handleEditName}
							aria-label="Edit name"
						>
							Edit
						</Button>
					</div>
				)}
			</div>

			{/* Password */}
			<div>
				{showPasswordForm ? (
					<div className="space-y-3">
						{session.hasPassword && (
							<div className="space-y-1">
								<Label htmlFor="current-password">Current password</Label>
								<Input
									id="current-password"
									type="password"
									value={currentPassword}
									onChange={(e) => setCurrentPassword(e.target.value)}
									autoComplete="current-password"
								/>
							</div>
						)}

						<div className="space-y-1">
							<Label htmlFor="new-password">New password</Label>
							<Input
								id="new-password"
								type="password"
								value={newPassword}
								onChange={(e) => setNewPassword(e.target.value)}
								autoComplete="new-password"
							/>
						</div>

						<div className="space-y-1">
							<Label htmlFor="confirm-new-password">Confirm new password</Label>
							<Input
								id="confirm-new-password"
								type="password"
								value={confirmNewPassword}
								onChange={(e) => setConfirmNewPassword(e.target.value)}
								autoComplete="new-password"
							/>
						</div>

						{passwordError && (
							<p className="text-destructive text-sm" role="alert">
								{passwordError}
							</p>
						)}

						<div className="flex gap-2">
							<Button
								size="sm"
								disabled={passwordSubmitting}
								onClick={handlePasswordSubmit}
								data-testid="password-submit"
							>
								{passwordSubmitting ? "Saving..." : "Save password"}
							</Button>
							<Button
								size="sm"
								variant="outline"
								onClick={() => setShowPasswordForm(false)}
							>
								Cancel
							</Button>
						</div>
					</div>
				) : (
					<div className="flex items-center gap-2">
						<span className="text-muted-foreground text-sm">Password:</span>
						<Button
							size="sm"
							variant="outline"
							onClick={handleOpenPasswordForm}
						>
							{session.hasPassword ? "Change password" : "Set a password"}
						</Button>
					</div>
				)}
			</div>

			{/* Separator */}
			<hr className="border-border" />

			{/* Sign out buttons */}
			{showSignOutAllConfirm ? (
				<div className="space-y-2">
					<p className="text-muted-foreground text-sm">
						This will sign you out everywhere, including other browsers and
						devices. Are you sure?
					</p>
					<div className="flex gap-2">
						<Button
							size="sm"
							variant="destructive"
							onClick={handleSignOutAllDevices}
						>
							Confirm
						</Button>
						<Button
							size="sm"
							variant="outline"
							onClick={() => setShowSignOutAllConfirm(false)}
						>
							Cancel
						</Button>
					</div>
				</div>
			) : (
				<div className="flex gap-2">
					<Button size="sm" variant="outline" onClick={handleSignOut}>
						Sign out
					</Button>
					<Button
						size="sm"
						variant="outline"
						onClick={() => setShowSignOutAllConfirm(true)}
					>
						Sign out of all devices
					</Button>
				</div>
			)}
		</div>
	);
}
