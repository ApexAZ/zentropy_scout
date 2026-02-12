"use client";

/**
 * Bullet item displaying a single accomplishment bullet.
 *
 * REQ-012 §6.3.3: Each bullet shows text with edit/delete actions.
 * REQ-001 §3.2: Optional metrics field shown as a badge.
 */

import { Pencil, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Bullet } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BulletItemProps {
	bullet: Bullet;
	onEdit: (bullet: Bullet) => void;
	onDelete: (bullet: Bullet) => void;
	dragHandle: React.ReactNode | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BulletItem({
	bullet,
	onEdit,
	onDelete,
	dragHandle,
}: BulletItemProps) {
	return (
		<div className="flex items-start gap-2 rounded-md border p-3">
			{dragHandle}
			<div className="min-w-0 flex-1">
				<p className="text-sm">{bullet.text}</p>
				{bullet.metrics && (
					<span className="bg-muted text-muted-foreground mt-1 inline-block rounded px-2 py-0.5 text-xs">
						{bullet.metrics}
					</span>
				)}
			</div>
			<div className="flex shrink-0 gap-1">
				<Button
					variant="ghost"
					size="icon"
					className="h-7 w-7"
					onClick={() => onEdit(bullet)}
					aria-label="Edit bullet"
				>
					<Pencil className="h-3 w-3" />
				</Button>
				<Button
					variant="ghost"
					size="icon"
					className="h-7 w-7"
					onClick={() => onDelete(bullet)}
					aria-label="Delete bullet"
				>
					<Trash2 className="h-3 w-3" />
				</Button>
			</div>
		</div>
	);
}
