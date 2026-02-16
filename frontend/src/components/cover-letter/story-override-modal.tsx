"use client";

/**
 * Story override modal for cover letter regeneration.
 *
 * REQ-012 §10.5: Modal showing all achievement stories split into
 * "Currently selected" and "Available" groups with relevance scores,
 * allowing users to override the agent's story selection.
 */

import { useCallback, useMemo, useState } from "react";
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
// Types
// ---------------------------------------------------------------------------

interface StoryWithScore {
	id: string;
	title: string;
	relevance_score: number;
}

interface StoryOverrideModalProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	coverLetterId: string;
	stories: StoryWithScore[];
	selectedStoryIds: string[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StoryOverrideModal({
	open,
	onOpenChange,
	coverLetterId,
	stories,
	selectedStoryIds,
}: Readonly<StoryOverrideModalProps>) {
	const queryClient = useQueryClient();

	// -----------------------------------------------------------------------
	// Local state
	// -----------------------------------------------------------------------

	const [selected, setSelected] = useState<Set<string>>(
		() => new Set(selectedStoryIds),
	);
	const [isSubmitting, setIsSubmitting] = useState(false);

	// -----------------------------------------------------------------------
	// Derived state
	// -----------------------------------------------------------------------

	const { selectedStories, availableStories } = useMemo(() => {
		const sel: StoryWithScore[] = [];
		const avail: StoryWithScore[] = [];

		for (const story of stories) {
			if (selected.has(story.id)) {
				sel.push(story);
			} else {
				avail.push(story);
			}
		}

		sel.sort((a, b) => b.relevance_score - a.relevance_score);
		avail.sort((a, b) => b.relevance_score - a.relevance_score);

		return { selectedStories: sel, availableStories: avail };
	}, [stories, selected]);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const resetState = useCallback(() => {
		setSelected(new Set(selectedStoryIds));
		setIsSubmitting(false);
	}, [selectedStoryIds]);

	const handleOpenChange = useCallback(
		(nextOpen: boolean) => {
			if (!nextOpen) {
				resetState();
			}
			onOpenChange(nextOpen);
		},
		[onOpenChange, resetState],
	);

	const handleToggle = useCallback((storyId: string) => {
		setSelected((prev) => {
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
				selected_story_ids: Array.from(selected),
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
	}, [coverLetterId, selected, queryClient, handleOpenChange]);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent className="sm:max-w-lg">
				<DialogHeader>
					<DialogTitle>Select Stories</DialogTitle>
					<DialogDescription>
						Override the agent&apos;s story selection for this cover letter.
					</DialogDescription>
				</DialogHeader>

				{/* Currently selected */}
				{selectedStories.length > 0 && (
					<div>
						<p className="mb-2 text-sm font-semibold">Currently selected:</p>
						<div data-testid="selected-stories" className="space-y-2">
							{selectedStories.map((story) => (
								<label
									key={story.id}
									className="flex items-center gap-2 text-sm"
								>
									<Checkbox
										checked={true}
										onCheckedChange={() => handleToggle(story.id)}
									/>
									<span
										data-testid="story-title"
										className="flex-1 font-medium"
									>
										{story.title}
									</span>
									<span className="text-muted-foreground text-xs">
										{story.relevance_score}pt
									</span>
								</label>
							))}
						</div>
					</div>
				)}

				{/* Available */}
				{availableStories.length > 0 && (
					<div>
						<p className="mb-2 text-sm font-semibold">Available:</p>
						<div data-testid="available-stories" className="space-y-2">
							{availableStories.map((story) => (
								<label
									key={story.id}
									className="flex items-center gap-2 text-sm"
								>
									<Checkbox
										checked={false}
										onCheckedChange={() => handleToggle(story.id)}
									/>
									<span data-testid="story-title" className="flex-1">
										{story.title}
									</span>
									<span className="text-muted-foreground text-xs">
										{story.relevance_score}pt
									</span>
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
						disabled={isSubmitting || selected.size === 0}
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
						{isSubmitting ? "Regenerating..." : "Regenerate with selection"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
