/**
 * Account settings section — displayed at the top of the Settings page.
 *
 * REQ-013 §8.3a: Email display + verified badge, name edit,
 * password change/set, sign out, sign out all devices.
 */

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, apiPatch, apiPost } from "@/lib/api-client";
import { useSession } from "@/lib/auth-provider";
import { showToast } from "@/lib/toast";

// ---------------------------------------------------------------------------
// Password policy (matches registration page — REQ-013 §10.8)
// ---------------------------------------------------------------------------

const PASSWORD_REQUIREMENTS = [
	{
		key: "length",
		label: "At least 8 characters",
		test: (p: string) => p.length >= 8,
	},
	{
		key: "letter",
		label: "At least one letter",
		test: (p: string) => /[a-zA-Z]/.test(p),
	},
	{
		key: "number",
		label: "At least one number",
		test: (p: string) => /\d/.test(p),
	},
	{
		key: "special",
		label: "At least one special character",
		test: (p: string) => /[^a-zA-Z\d]/.test(p),
	},
];

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
// Component
// ---------------------------------------------------------------------------

export function AccountSection() {
	const { session, logout, logoutAllDevices } = useSession();

	// Name editing state
	const [editingName, setEditingName] = useState(false);
	const [nameValue, setNameValue] = useState(session?.name ?? "");
	const [displayName, setDisplayName] = useState(session?.name ?? "");

	// Sync name state when session loads (hooks run before null guard)
	useEffect(() => {
		if (session?.name != null) {
			setDisplayName(session.name);
			setNameValue(session.name);
		}
	}, [session?.name]);

	// Auto-open password form when arriving from forgot-password flow.
	// useState initial value only applies on first render (when session is null),
	// so we need useEffect to react when canResetPassword becomes true.
	useEffect(() => {
		if (session?.canResetPassword) {
			setShowPasswordForm(true);
		}
	}, [session?.canResetPassword]);

	// Password form state — auto-open when arriving from forgot-password flow
	const [showPasswordForm, setShowPasswordForm] = useState(
		session?.canResetPassword ?? false,
	);
	const [currentPassword, setCurrentPassword] = useState("");
	const [newPassword, setNewPassword] = useState("");
	const [confirmNewPassword, setConfirmNewPassword] = useState("");
	const [passwordError, setPasswordError] = useState<string | null>(null);
	const [passwordSubmitting, setPasswordSubmitting] = useState(false);
	const [passwordResetSuccess, setPasswordResetSuccess] = useState(false);

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
			const needsCurrentPassword =
				session.hasPassword && !session.canResetPassword;
			await apiPost("/auth/change-password", {
				current_password: needsCurrentPassword ? currentPassword : null,
				new_password: newPassword,
			});
			setShowPasswordForm(false);
			setPasswordResetSuccess(true);
			showToast.success("Password updated");
		} catch (err) {
			if (err instanceof ApiError && err.status === 401) {
				setPasswordError("Current password is incorrect");
			} else if (err instanceof ApiError && err.code === "PASSWORD_BREACHED") {
				setPasswordError(
					"This password has appeared in a data breach. Please choose a different one.",
				);
			} else if (err instanceof ApiError && err.status === 429) {
				setPasswordError(
					"Too many password change attempts. Please wait an hour before trying again.",
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
						{session.canResetPassword && (
							<p
								className="text-destructive text-sm font-medium"
								role="alert"
								data-testid="reset-password-banner"
							>
								Please set a new password.
							</p>
						)}

						{session.hasPassword && !session.canResetPassword && (
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

						{/* Password strength indicator */}
						<ul
							className="space-y-1 text-xs"
							aria-label="Password requirements"
						>
							{PASSWORD_REQUIREMENTS.map((req) => {
								const met = req.test(newPassword);
								return (
									<li
										key={req.key}
										data-testid={`req-${req.key}`}
										data-met={met ? "true" : "false"}
										className={met ? "text-green-600" : "text-muted-foreground"}
									>
										{met ? "\u2713" : "\u2022"} {req.label}
									</li>
								);
							})}
						</ul>

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
					<div className="space-y-2">
						{passwordResetSuccess && (
							<output
								className="text-sm font-medium text-green-600"
								data-testid="reset-password-success"
							>
								Password updated successfully.
							</output>
						)}
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
						<Button size="sm" variant="destructive" onClick={logoutAllDevices}>
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
					<Button size="sm" variant="outline" onClick={logout}>
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
