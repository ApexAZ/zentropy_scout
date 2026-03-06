"use client";

/**
 * Resume content toggle view: Preview, Edit, and no-content states.
 *
 * REQ-026 §6.1: Toggle view (Preview/Edit) with TipTap editor.
 * REQ-026 §6.2: Action buttons per mode.
 * REQ-026 §6.3: Content preview via read-only TipTap.
 * REQ-026 §4.2: Generation options panel integration.
 * REQ-026 §4.7: Regeneration via options panel.
 */

import { useCallback, useMemo, useState } from "react";
import {
	FileText,
	Loader2,
	Pencil,
	RefreshCw,
	Sparkles,
	User,
} from "lucide-react";

import { showToast } from "@/lib/toast";
import type {
	GenerateResumeResponse,
	GenerationMethod,
	GenerationOptions,
} from "@/types/resume-generation";
import { useAutoSave } from "@/hooks/use-auto-save";
import { GenerationOptionsPanel } from "@/components/editor/generation-options-panel";
import { EditorStatusBar } from "@/components/editor/editor-status-bar";
import { PersonaReferencePanel } from "@/components/editor/persona-reference-panel";
import { ResumeEditor } from "@/components/editor/resume-editor";
import { ExportButtons } from "@/components/resume/export-buttons";
import { Button } from "@/components/ui/button";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
	SheetTrigger,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ResumeContentViewProps {
	resumeId: string;
	personaId: string;
	markdownContent: string | null;
	isGenerating: boolean;
	onGenerate: (
		method: GenerationMethod,
		options?: GenerationOptions,
	) => Promise<GenerateResumeResponse | null>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ICON_CLASS = "mr-1 h-4 w-4";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function countWords(text: string): number {
	const trimmed = text.trim();
	if (!trimmed) return 0;
	return trimmed.split(/\s+/).length;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ResumeContentView({
	resumeId,
	personaId,
	markdownContent,
	isGenerating,
	onGenerate,
}: Readonly<ResumeContentViewProps>) {
	const [viewMode, setViewMode] = useState<"preview" | "edit">("preview");
	const [editorContent, setEditorContent] = useState(markdownContent ?? "");
	const [showOptionsPanel, setShowOptionsPanel] = useState(false);
	const [lastOptions, setLastOptions] = useState<GenerationOptions | undefined>(
		undefined,
	);

	const { saveStatus } = useAutoSave({
		content: editorContent,
		resumeId,
		enabled: viewMode === "edit",
	});

	const wordCount = useMemo(() => countWords(editorContent), [editorContent]);

	const handleAiGenerate = useCallback(() => {
		setShowOptionsPanel(true);
	}, []);

	const handleTemplateFill = useCallback(async () => {
		await onGenerate("template_fill");
	}, [onGenerate]);

	const handleGenerateFromPanel = useCallback(
		async (options: GenerationOptions) => {
			setLastOptions(options);
			const result = await onGenerate("ai", options);
			if (result) {
				setShowOptionsPanel(false);
			} else {
				// 402 credit failure — offer template fill as fallback
				showToast.info(
					'Tip: "Start from Template" is free and doesn\'t require credits.',
					{ id: "credit-fallback-hint" },
				);
			}
		},
		[onGenerate],
	);

	const handleCancelPanel = useCallback(() => {
		setShowOptionsPanel(false);
	}, []);

	const handleRegenerate = useCallback(() => {
		setShowOptionsPanel(true);
	}, []);

	// -----------------------------------------------------------------------
	// Options panel (initial generation or regeneration)
	// -----------------------------------------------------------------------

	if (showOptionsPanel) {
		return (
			<div className="mb-8" data-testid="generation-panel-container">
				<GenerationOptionsPanel
					onGenerate={handleGenerateFromPanel}
					onCancel={handleCancelPanel}
					isGenerating={isGenerating}
					defaultOptions={lastOptions}
				/>
			</div>
		);
	}

	// -----------------------------------------------------------------------
	// No-content state
	// -----------------------------------------------------------------------

	if (!markdownContent) {
		if (isGenerating) {
			return (
				<div
					data-testid="generating-state"
					className="mb-8 flex flex-col items-center justify-center rounded-md border border-dashed py-12"
				>
					<Loader2 className="text-muted-foreground mb-2 h-10 w-10 animate-spin" />
					<p className="text-muted-foreground text-center">
						Generating your resume...
					</p>
				</div>
			);
		}

		return (
			<div
				data-testid="no-content-prompt"
				className="mb-8 flex flex-col items-center justify-center rounded-md border border-dashed py-12"
			>
				<FileText className="text-muted-foreground mb-2 h-10 w-10" />
				<p className="text-muted-foreground mb-4 text-center">
					Generate your resume or start from a template to get started.
				</p>
				<div className="flex gap-2">
					<Button variant="outline" onClick={handleAiGenerate}>
						<Sparkles className={ICON_CLASS} />
						Generate with AI
					</Button>
					<Button variant="outline" onClick={handleTemplateFill}>
						<FileText className={ICON_CLASS} />
						Start from Template
					</Button>
				</div>
			</div>
		);
	}

	// -----------------------------------------------------------------------
	// Content view with toggle
	// -----------------------------------------------------------------------

	return (
		<div className="mb-8">
			<Tabs
				value={viewMode}
				onValueChange={(v) => setViewMode(v as "preview" | "edit")}
			>
				<TabsList>
					<TabsTrigger value="preview">Preview</TabsTrigger>
					<TabsTrigger value="edit">Edit</TabsTrigger>
				</TabsList>
				<TabsContent value="preview">
					<div className="rounded-md border">
						<ResumeEditor initialContent={markdownContent} editable={false} />
					</div>
				</TabsContent>
				<TabsContent value="edit">
					<div className="flex gap-4">
						{/* Desktop: inline persona panel */}
						<aside
							className="bg-card hidden w-72 shrink-0 overflow-y-auto rounded-lg border p-3 md:block"
							data-testid="persona-panel-desktop"
						>
							<PersonaReferencePanel personaId={personaId} />
						</aside>

						{/* Mobile: Sheet toggle */}
						<div className="mb-2 md:hidden">
							<Sheet>
								<SheetTrigger asChild>
									<Button
										variant="outline"
										size="sm"
										data-testid="persona-panel-toggle"
									>
										<User className={ICON_CLASS} />
										Persona
									</Button>
								</SheetTrigger>
								<SheetContent side="left" className="w-72">
									<SheetHeader>
										<SheetTitle>Persona Reference</SheetTitle>
										<SheetDescription>
											Click items to copy to clipboard
										</SheetDescription>
									</SheetHeader>
									<div className="overflow-y-auto px-4 pb-4">
										<PersonaReferencePanel personaId={personaId} />
									</div>
								</SheetContent>
							</Sheet>
						</div>

						{/* Editor */}
						<div className="min-w-0 flex-1 rounded-md border">
							<ResumeEditor
								initialContent={markdownContent}
								editable={true}
								onChange={setEditorContent}
							/>
							<EditorStatusBar wordCount={wordCount} saveStatus={saveStatus} />
						</div>
					</div>
				</TabsContent>
			</Tabs>

			{/* Action buttons per mode */}
			<div className="mt-4 flex items-center gap-2">
				{viewMode === "preview" ? (
					<>
						<Button variant="outline" onClick={() => setViewMode("edit")}>
							<Pencil className={ICON_CLASS} />
							Edit
						</Button>
						<Button variant="outline" onClick={handleRegenerate}>
							<RefreshCw className={ICON_CLASS} />
							Regenerate
						</Button>
					</>
				) : (
					<Button onClick={() => setViewMode("preview")}>Done Editing</Button>
				)}
				<ExportButtons resumeId={resumeId} />
			</div>
		</div>
	);
}
