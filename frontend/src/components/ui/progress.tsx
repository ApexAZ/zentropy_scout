"use client";

/**
 * Progress bar UI primitive.
 *
 * Built on Radix UI Progress primitive following shadcn/ui patterns.
 * Displays a horizontal progress indicator with ARIA attributes.
 */

import * as React from "react";
import { Progress as ProgressPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";

/**
 * Accessible progress bar with animated indicator.
 *
 * @param props.value - Progress percentage (0–100). Defaults to 0.
 * @param props.className - Additional CSS classes on the root track.
 */
function Progress({
	className,
	value,
	...props
}: React.ComponentProps<typeof ProgressPrimitive.Root>) {
	return (
		<ProgressPrimitive.Root
			data-slot="progress"
			className={cn(
				"bg-primary/20 relative h-2 w-full overflow-hidden rounded-full",
				className,
			)}
			value={value}
			{...props}
		>
			<ProgressPrimitive.Indicator
				data-slot="progress-indicator"
				className="bg-primary h-full w-full flex-1 transition-all"
				style={{
					transform: `translateX(-${100 - Math.min(100, Math.max(0, value ?? 0))}%)`,
				}}
			/>
		</ProgressPrimitive.Root>
	);
}

export { Progress };
