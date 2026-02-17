/**
 * Reusable AlertDialog wrapper for form dialogs.
 *
 * Provides the standard dialog chrome (overlay, content panel, title,
 * description, cancel/save buttons) used by rejection-details-dialog
 * and offer-details-dialog.
 */

import type { ReactNode } from "react";
import { AlertDialog as AlertDialogPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FormAlertDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	title: string;
	description: string;
	loading?: boolean;
	onConfirm: () => void;
	children: ReactNode;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function FormAlertDialog({
	open,
	onOpenChange,
	title,
	description,
	loading = false,
	onConfirm,
	children,
}: Readonly<FormAlertDialogProps>) {
	return (
		<AlertDialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
			<AlertDialogPrimitive.Portal>
				<AlertDialogPrimitive.Overlay className="data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/50" />
				<AlertDialogPrimitive.Content
					className={cn(
						"bg-background data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 fixed top-[50%] left-[50%] z-50 grid w-full max-w-[calc(100%-2rem)] translate-x-[-50%] translate-y-[-50%] gap-4 rounded-lg border p-6 shadow-lg duration-200 outline-none sm:max-w-lg",
					)}
				>
					<div className="flex flex-col gap-2 text-center sm:text-left">
						<AlertDialogPrimitive.Title className="text-lg leading-none font-semibold">
							{title}
						</AlertDialogPrimitive.Title>
						<AlertDialogPrimitive.Description className="text-muted-foreground text-sm">
							{description}
						</AlertDialogPrimitive.Description>
					</div>

					{children}

					<div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
						<AlertDialogPrimitive.Cancel asChild>
							<Button variant="outline" disabled={loading}>
								Cancel
							</Button>
						</AlertDialogPrimitive.Cancel>
						<Button disabled={loading} onClick={onConfirm}>
							Save
						</Button>
					</div>
				</AlertDialogPrimitive.Content>
			</AlertDialogPrimitive.Portal>
		</AlertDialogPrimitive.Root>
	);
}

export { FormAlertDialog };
export type { FormAlertDialogProps };
