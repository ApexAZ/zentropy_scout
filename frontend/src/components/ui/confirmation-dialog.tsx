"use client";

/**
 * Pre-composed confirmation dialog with optional destructive variant.
 *
 * REQ-012 §7.5: Deletion confirmation dialogs.
 * REQ-012 §11.3: Status transition confirmations.
 *
 * Built on Radix UI AlertDialog — blocks interaction until the user
 * explicitly confirms or cancels. Unlike Dialog, clicking the overlay
 * does NOT close an AlertDialog.
 */

import * as React from "react";
import { AlertDialog as AlertDialogPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";

import { Button } from "./button";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ConfirmationDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	title: string;
	description: string;
	onConfirm: () => void;
	confirmLabel?: string;
	cancelLabel?: string;
	variant?: "default" | "destructive";
	loading?: boolean;
	className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ConfirmationDialog({
	open,
	onOpenChange,
	title,
	description,
	onConfirm,
	confirmLabel = "Confirm",
	cancelLabel = "Cancel",
	variant = "default",
	loading = false,
	className,
}: ConfirmationDialogProps) {
	return (
		<AlertDialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
			<AlertDialogPrimitive.Portal>
				<AlertDialogPrimitive.Overlay
					data-slot="confirmation-dialog-overlay"
					className="data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/50"
				/>
				<AlertDialogPrimitive.Content
					data-slot="confirmation-dialog"
					className={cn(
						"bg-background data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 fixed top-[50%] left-[50%] z-50 grid w-full max-w-[calc(100%-2rem)] translate-x-[-50%] translate-y-[-50%] gap-4 rounded-lg border p-6 shadow-lg duration-200 outline-none sm:max-w-lg",
						className,
					)}
				>
					<div className="flex flex-col gap-2 text-center sm:text-left">
						<AlertDialogPrimitive.Title
							data-slot="confirmation-dialog-title"
							className="text-lg leading-none font-semibold"
						>
							{title}
						</AlertDialogPrimitive.Title>
						<AlertDialogPrimitive.Description
							data-slot="confirmation-dialog-description"
							className="text-muted-foreground text-sm"
						>
							{description}
						</AlertDialogPrimitive.Description>
					</div>
					<div
						data-slot="confirmation-dialog-footer"
						className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"
					>
						<AlertDialogPrimitive.Cancel asChild>
							<Button variant="outline" disabled={loading}>
								{cancelLabel}
							</Button>
						</AlertDialogPrimitive.Cancel>
						<Button
							variant={variant === "destructive" ? "destructive" : "default"}
							disabled={loading}
							onClick={onConfirm}
						>
							{confirmLabel}
						</Button>
					</div>
				</AlertDialogPrimitive.Content>
			</AlertDialogPrimitive.Portal>
		</AlertDialogPrimitive.Root>
	);
}
