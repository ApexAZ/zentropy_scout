"use client";

/**
 * Creation method choice for the new resume wizard.
 *
 * REQ-026 §3.1–§3.2: Two creation paths — "Generate with AI" (requires credits)
 * vs "Start from Template" (free, deterministic fill).
 */

import { FileText, Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CreationMethod = "ai" | "template_fill";

interface CreationMethodButtonsProps {
	isCreating: boolean;
	canSubmit: boolean;
	onCreate: (method: CreationMethod) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CreationMethodButtons({
	isCreating,
	canSubmit,
	onCreate,
}: Readonly<CreationMethodButtonsProps>) {
	return (
		<div className="mt-8 mb-4">
			<h2 className="mb-3 text-sm font-medium">How would you like to start?</h2>
			<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<Button
					variant="outline"
					className="h-auto flex-col gap-2 p-4"
					onClick={() => onCreate("ai")}
					disabled={!canSubmit}
				>
					{isCreating ? (
						<>
							<Loader2 className="h-5 w-5 animate-spin" />
							<span>Creating...</span>
						</>
					) : (
						<>
							<Sparkles className="h-5 w-5" />
							<span className="font-medium">Generate with AI</span>
							<span className="text-muted-foreground text-xs">
								AI composes a polished resume (requires credits)
							</span>
						</>
					)}
				</Button>
				<Button
					variant="outline"
					className="h-auto flex-col gap-2 p-4"
					onClick={() => onCreate("template_fill")}
					disabled={!canSubmit}
				>
					{isCreating ? (
						<>
							<Loader2 className="h-5 w-5 animate-spin" />
							<span>Creating...</span>
						</>
					) : (
						<>
							<FileText className="h-5 w-5" />
							<span className="font-medium">Start from Template</span>
							<span className="text-muted-foreground text-xs">
								Your data filled into template (free)
							</span>
						</>
					)}
				</Button>
			</div>
		</div>
	);
}
