"use client";

/**
 * Resume content toggle view: Preview, Edit, and no-content states.
 *
 * REQ-026 §6.1: Toggle view (Preview/Edit) with TipTap editor.
 * REQ-026 §6.2: Action buttons per mode.
 * REQ-026 §6.3: Content preview via read-only TipTap.
 */

import { useMemo, useState } from "react";
import { Download, FileText, Pencil, Sparkles, User } from "lucide-react";

import { buildUrl } from "@/lib/api-client";
import { useAutoSave } from "@/hooks/use-auto-save";
import { EditorStatusBar } from "@/components/editor/editor-status-bar";
import { PersonaReferencePanel } from "@/components/editor/persona-reference-panel";
import { ResumeEditor } from "@/components/editor/resume-editor";
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

function ExportButtons({ resumeId }: Readonly<{ resumeId: string }>) {
	return (
		<>
			<Button
				variant="outline"
				onClick={() =>
					window.open(
						buildUrl(`/base-resumes/${resumeId}/export/pdf`),
						"_blank",
						"noopener,noreferrer",
					)
				}
			>
				<Download className={ICON_CLASS} />
				Export PDF
			</Button>
			<Button
				variant="outline"
				onClick={() =>
					window.open(
						buildUrl(`/base-resumes/${resumeId}/export/docx`),
						"_blank",
						"noopener,noreferrer",
					)
				}
			>
				<FileText className={ICON_CLASS} />
				Export DOCX
			</Button>
		</>
	);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ResumeContentView({
	resumeId,
	personaId,
	markdownContent,
}: Readonly<ResumeContentViewProps>) {
	const [viewMode, setViewMode] = useState<"preview" | "edit">("preview");
	const [editorContent, setEditorContent] = useState(markdownContent ?? "");

	const { saveStatus } = useAutoSave({
		content: editorContent,
		resumeId,
		enabled: viewMode === "edit",
	});

	const wordCount = useMemo(() => countWords(editorContent), [editorContent]);

	// No-content state
	if (!markdownContent) {
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
					<Button variant="outline" disabled>
						<Sparkles className={ICON_CLASS} />
						Generate with AI
					</Button>
					<Button variant="outline" disabled>
						<FileText className={ICON_CLASS} />
						Start from Template
					</Button>
				</div>
			</div>
		);
	}

	// Content view with toggle
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
							className="bg-card hidden w-72 shrink-0 overflow-y-auto rounded-md border p-3 md:block"
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
						<Button variant="outline" disabled>
							<Sparkles className={ICON_CLASS} />
							Generate with AI
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
