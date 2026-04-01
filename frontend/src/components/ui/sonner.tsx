"use client";

/**
 * @fileoverview Toast notification container wrapping Sonner with project defaults.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-012 §13.5, §13.8: Toast notifications with rich colors, close buttons,
 * Lucide icons matching the design system, and aria-live="polite".
 *
 * Coordinates with:
 * - (no local module dependencies — wraps third-party Sonner with project defaults)
 *
 * Called by / Used by:
 * - app/layout.tsx: root layout toast container
 */

import { CircleAlert, CircleCheck, Info, TriangleAlert } from "lucide-react";
import { Toaster as SonnerToaster, type ToasterProps } from "sonner";

const ICON_CLASS = "size-5";
function Toaster(props: Readonly<ToasterProps>) {
	return (
		<SonnerToaster
			richColors
			closeButton
			icons={{
				success: <CircleCheck className={ICON_CLASS} />,
				error: <CircleAlert className={ICON_CLASS} />,
				warning: <TriangleAlert className={ICON_CLASS} />,
				info: <Info className={ICON_CLASS} />,
			}}
			toastOptions={{
				style: {
					"--normal-bg": "var(--popover)",
					"--normal-text": "var(--popover-foreground)",
					"--normal-border": "var(--border)",
				} as React.CSSProperties,
			}}
			{...props}
		/>
	);
}

export { Toaster };
export type { ToasterProps } from "sonner";
