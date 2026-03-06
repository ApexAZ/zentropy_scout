"use client";

/**
 * TipTap-based rich text editor for resume markdown editing.
 *
 * REQ-025 §3.2: Client-side editor with markdown round-trip via
 * @tiptap/markdown, SSR-safe with immediatelyRender: false.
 */

import { useEffect } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Markdown } from "@tiptap/markdown";

import { EditorToolbar } from "@/components/editor/editor-toolbar";
import { isSafeUrl } from "@/lib/url-utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ResumeEditorProps {
	initialContent?: string;
	editable?: boolean;
	onChange?: (markdown: string) => void;
	placeholder?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EDITOR_PLACEHOLDER = "Start writing your resume...";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ResumeEditor({
	initialContent = "",
	editable = true,
	onChange,
	placeholder,
}: Readonly<ResumeEditorProps>) {
	const editor = useEditor({
		immediatelyRender: false,
		editable,
		content: initialContent || undefined,
		contentType: "markdown",
		extensions: [
			StarterKit.configure({
				heading: { levels: [1, 2, 3, 4] },
				codeBlock: false,
				code: false,
				link: {
					openOnClick: false,
					isAllowedUri: (url: string) => isSafeUrl(url),
					HTMLAttributes: {
						rel: "noopener noreferrer nofollow",
						target: "_blank",
					},
				},
			}),
			Markdown,
		],
		onUpdate: ({ editor: ed }) => {
			onChange?.(ed.getMarkdown());
		},
	});

	// Update editable state when prop changes
	useEffect(() => {
		if (editor && editor.isEditable !== editable) {
			editor.setEditable(editable);
		}
	}, [editor, editable]);

	const displayPlaceholder = placeholder ?? EDITOR_PLACEHOLDER;

	return (
		<div data-testid="resume-editor" className="flex flex-col">
			{editable && <EditorToolbar editor={editor} />}
			<div
				className="prose prose-sm max-w-none p-4"
				data-testid="editor-content"
			>
				{editor && !editor.getText().trim() && !editor.isFocused && (
					<p
						className="text-muted-foreground pointer-events-none absolute"
						data-testid="editor-placeholder"
					>
						{displayPlaceholder}
					</p>
				)}
				<EditorContent editor={editor} />
			</div>
		</div>
	);
}

export type { ResumeEditorProps };
