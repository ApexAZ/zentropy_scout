"use client";

/**
 * Sheet component built on Radix Dialog.
 *
 * REQ-012 §5.1: Side sheet for tablet/mobile chat panel overlay.
 * Follows shadcn/ui Sheet pattern — Portal + Overlay + side-positioned Content.
 */

import * as React from "react";
import { XIcon } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Sheet (Root)
// ---------------------------------------------------------------------------

function Sheet({
	...props
}: Readonly<React.ComponentProps<typeof DialogPrimitive.Root>>) {
	return <DialogPrimitive.Root data-slot="sheet" {...props} />;
}

// ---------------------------------------------------------------------------
// SheetTrigger
// ---------------------------------------------------------------------------

function SheetTrigger({
	...props
}: React.ComponentProps<typeof DialogPrimitive.Trigger>) {
	return <DialogPrimitive.Trigger data-slot="sheet-trigger" {...props} />;
}

// ---------------------------------------------------------------------------
// SheetPortal
// ---------------------------------------------------------------------------

function SheetPortal({
	...props
}: Readonly<React.ComponentProps<typeof DialogPrimitive.Portal>>) {
	return <DialogPrimitive.Portal data-slot="sheet-portal" {...props} />;
}

// ---------------------------------------------------------------------------
// SheetClose
// ---------------------------------------------------------------------------

function SheetClose({
	...props
}: React.ComponentProps<typeof DialogPrimitive.Close>) {
	return <DialogPrimitive.Close data-slot="sheet-close" {...props} />;
}

// ---------------------------------------------------------------------------
// SheetOverlay
// ---------------------------------------------------------------------------

function SheetOverlay({
	className,
	...props
}: React.ComponentProps<typeof DialogPrimitive.Overlay>) {
	return (
		<DialogPrimitive.Overlay
			data-slot="sheet-overlay"
			className={cn(
				"data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/50",
				className,
			)}
			{...props}
		/>
	);
}

// ---------------------------------------------------------------------------
// SheetContent
// ---------------------------------------------------------------------------

const sheetContentVariants: Record<string, string> = {
	top: "data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top inset-x-0 top-0 border-b",
	right:
		"data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right inset-y-0 right-0 h-full border-l",
	bottom:
		"data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom inset-x-0 bottom-0 border-t",
	left: "data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left inset-y-0 left-0 h-full border-r",
};

function SheetContent({
	className,
	children,
	side = "right",
	...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & {
	side?: "top" | "right" | "bottom" | "left";
}) {
	return (
		<SheetPortal>
			<SheetOverlay />
			<DialogPrimitive.Content
				data-slot="sheet-content"
				data-side={side}
				className={cn(
					"bg-background data-[state=open]:animate-in data-[state=closed]:animate-out fixed z-50 flex flex-col gap-4 shadow-lg transition ease-in-out data-[state=closed]:duration-300 data-[state=open]:duration-500",
					sheetContentVariants[side],
					className,
				)}
				{...props}
			>
				{children}
				<DialogPrimitive.Close
					data-slot="sheet-close"
					className="ring-offset-background focus:ring-ring data-[state=open]:bg-secondary absolute top-4 right-4 rounded-xs opacity-70 transition-opacity hover:opacity-100 focus:ring-2 focus:ring-offset-2 focus:outline-hidden disabled:pointer-events-none"
				>
					<XIcon className="size-4" />
					<span className="sr-only">Close</span>
				</DialogPrimitive.Close>
			</DialogPrimitive.Content>
		</SheetPortal>
	);
}

// ---------------------------------------------------------------------------
// SheetHeader
// ---------------------------------------------------------------------------

function SheetHeader({ className, ...props }: React.ComponentProps<"div">) {
	return (
		<div
			data-slot="sheet-header"
			className={cn("flex flex-col gap-1.5 p-4", className)}
			{...props}
		/>
	);
}

// ---------------------------------------------------------------------------
// SheetFooter
// ---------------------------------------------------------------------------

function SheetFooter({ className, ...props }: React.ComponentProps<"div">) {
	return (
		<div
			data-slot="sheet-footer"
			className={cn("mt-auto flex flex-col gap-2 p-4", className)}
			{...props}
		/>
	);
}

// ---------------------------------------------------------------------------
// SheetTitle
// ---------------------------------------------------------------------------

function SheetTitle({
	className,
	...props
}: React.ComponentProps<typeof DialogPrimitive.Title>) {
	return (
		<DialogPrimitive.Title
			data-slot="sheet-title"
			className={cn("text-foreground text-lg font-semibold", className)}
			{...props}
		/>
	);
}

// ---------------------------------------------------------------------------
// SheetDescription
// ---------------------------------------------------------------------------

function SheetDescription({
	className,
	...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
	return (
		<DialogPrimitive.Description
			data-slot="sheet-description"
			className={cn("text-muted-foreground text-sm", className)}
			{...props}
		/>
	);
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

export {
	Sheet,
	SheetClose,
	SheetContent,
	SheetDescription,
	SheetFooter,
	SheetHeader,
	SheetOverlay,
	SheetPortal,
	SheetTitle,
	SheetTrigger,
};
