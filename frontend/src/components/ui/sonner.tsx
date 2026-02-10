"use client";

import { CircleAlert, CircleCheck, Info, TriangleAlert } from "lucide-react";
import { Toaster as SonnerToaster, type ToasterProps } from "sonner";

const ICON_CLASS = "size-5";

/**
 * Toast notification container — REQ-012 §13.5, §13.8.
 *
 * Wraps Sonner's `<Toaster>` with project defaults:
 * - `richColors` for semantic variant styling
 * - `closeButton` on every toast
 * - Lucide icons matching the design system
 * - `aria-live="polite"` (built into Sonner)
 */
function Toaster(props: ToasterProps) {
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
export type { ToasterProps };
