"use client";

/**
 * Regeneration feedback modal for cover letter re-generation.
 *
 * REQ-012 §10.4: Feedback panel with free-text input, story exclusion
 * checkboxes, and quick option chips.
 */

import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { apiPost } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_FEEDBACK_LENGTH = 500;

const START_FRESH = "Start fresh" as const;

const QUICK_OPTIONS = [
	"Shorter",
	"Longer",
	"More formal",
	"Less formal",
	"More technical",
	START_FRESH,
] as const;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RegenerationFeedbackModalProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	coverLetterId: string;
	usedStories: { id: string; title: string }[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RegenerationFeedbackModal({
	open,
	onOpenChange,
	coverLetterId,
	usedStories,
}: RegenerationFeedbackModalProps) {
	const queryClient = useQueryClient();

	// -----------------------------------------------------------------------
	// Local state
	// -----------------------------------------------------------------------

	const [feedbackText, setFeedbackText] = useState("");
	const [excludedStoryIds, setExcludedStoryIds] = useState<Set<string>>(
		new Set(),
	);
	const [startFresh, setStartFresh] = useState(false);
	const [isSubmitting, setIsSubmitting] = useState(false);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const resetState = useCallback(() => {
		setFeedbackText("");
		setExcludedStoryIds(new Set());
		setStartFresh(false);
		setIsSubmitting(false);
	}, []);

	const handleOpenChange = useCallback(
		(nextOpen: boolean) => {
			if (!nextOpen) {
				resetState();
			}
			onOpenChange(nextOpen);
		},
		[onOpenChange, resetState],
	);

	const handleTextChange = useCallback(
		(e: React.ChangeEvent<HTMLTextAreaElement>) => {
			setFeedbackText(e.target.value.slice(0, MAX_FEEDBACK_LENGTH));
		},
		[],
	);

	const handleChipClick = useCallback((option: string) => {
		if (option === START_FRESH) {
			setFeedbackText("");
			setExcludedStoryIds(new Set());
			setStartFresh(true);
			return;
		}

		setStartFresh(false);
		setFeedbackText((prev) => (prev ? `${prev}. ${option}` : option));
	}, []);

	const handleStoryToggle = useCallback((storyId: string) => {
		setExcludedStoryIds((prev) => {
			const next = new Set(prev);
			if (next.has(storyId)) {
				next.delete(storyId);
			} else {
				next.add(storyId);
			}
			return next;
		});
	}, []);

	const handleRegenerate = useCallback(async () => {
		setIsSubmitting(true);

		try {
			await apiPost(`/cover-letters/${coverLetterId}/regenerate`, {
				feedback_text: feedbackText,
				excluded_story_ids: Array.from(excludedStoryIds),
				start_fresh: startFresh,
			});
			await queryClient.invalidateQueries({
				queryKey: queryKeys.coverLetter(coverLetterId),
			});
			showToast.success("Regeneration started.");
			handleOpenChange(false);
		} catch (err) {
			setIsSubmitting(false);
			showToast.error(toFriendlyError(err));
		}
	}, [
		coverLetterId,
		feedbackText,
		excludedStoryIds,
		startFresh,
		queryClient,
		handleOpenChange,
	]);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent className="sm:max-w-lg">
				<DialogHeader>
					<DialogTitle>Regeneration Feedback</DialogTitle>
					<DialogDescription>
						Provide feedback to guide the next draft.
					</DialogDescription>
				</DialogHeader>

				{/* Feedback textarea */}
				<div>
					<label
						htmlFor="regeneration-feedback"
						className="mb-2 block text-sm font-semibold"
					>
						What would you like changed?
					</label>
					<textarea
						id="regeneration-feedback"
						value={feedbackText}
						onChange={handleTextChange}
						placeholder='e.g., "Make it less formal" or "Focus more on technical skills"'
						rows={4}
						maxLength={MAX_FEEDBACK_LENGTH}
						className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm"
					/>
					<p className="text-muted-foreground mt-1 text-xs">
						{feedbackText.length}/{MAX_FEEDBACK_LENGTH} characters
					</p>
				</div>

				{/* Quick option chips */}
				<div>
					<p className="mb-2 text-sm font-semibold">Quick options:</p>
					<div className="flex flex-wrap gap-2">
						{QUICK_OPTIONS.map((option) => (
							<Button
								key={option}
								type="button"
								variant="outline"
								size="sm"
								onClick={() => handleChipClick(option)}
							>
								{option}
							</Button>
						))}
					</div>
				</div>

				{/* Story exclusion checkboxes */}
				{usedStories.length > 0 && (
					<div>
						<p className="mb-2 text-sm font-semibold">Exclude stories:</p>
						<div className="space-y-2">
							{usedStories.map((story) => (
								<label
									key={story.id}
									className="flex items-center gap-2 text-sm"
								>
									<Checkbox
										checked={excludedStoryIds.has(story.id)}
										onCheckedChange={() => handleStoryToggle(story.id)}
									/>
									{story.title}
								</label>
							))}
						</div>
					</div>
				)}

				{/* Footer */}
				<DialogFooter>
					<Button
						type="button"
						variant="outline"
						onClick={() => handleOpenChange(false)}
					>
						Cancel
					</Button>
					<Button
						type="button"
						disabled={isSubmitting}
						onClick={handleRegenerate}
						className="gap-2"
					>
						{isSubmitting && (
							<Loader2
								data-testid="regenerate-spinner"
								className="h-4 w-4 animate-spin"
								aria-hidden="true"
							/>
						)}
						{isSubmitting ? "Regenerating..." : "Regenerate"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
