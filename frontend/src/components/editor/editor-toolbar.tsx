"use client";

/**
 * Formatting toolbar for the TipTap resume editor.
 *
 * REQ-025 §3.4: Button groups for text style, headings, lists,
 * insert (HR, link), and undo/redo with active state highlighting.
 */

import { useCallback, useState } from "react";
import type { Editor } from "@tiptap/react";
import {
	Bold,
	Heading1,
	Heading2,
	Heading3,
	Heading4,
	Italic,
	Link,
	List,
	ListOrdered,
	Minus,
	Redo,
	Undo,
} from "lucide-react";

import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface EditorToolbarProps {
	editor: Editor | null;
}

// ---------------------------------------------------------------------------
// Link Dialog
// ---------------------------------------------------------------------------

function LinkDialog({
	onSubmit,
	onCancel,
	initialUrl,
}: Readonly<{
	onSubmit: (url: string) => void;
	onCancel: () => void;
	initialUrl: string;
}>) {
	const [url, setUrl] = useState(initialUrl);

	const handleSubmit = useCallback(
		(e: React.FormEvent) => {
			e.preventDefault();
			onSubmit(url);
		},
		[onSubmit, url],
	);

	return (
		<form
			onSubmit={handleSubmit}
			className="flex items-center gap-2"
			data-testid="link-dialog"
		>
			<input
				type="url"
				value={url}
				onChange={(e) => setUrl(e.target.value)}
				placeholder="https://example.com"
				className="border-input bg-background rounded-md border px-2 py-1 text-sm"
				data-testid="link-url-input"
			/>
			<Button type="submit" size="sm" data-testid="link-submit">
				Apply
			</Button>
			<Button
				type="button"
				size="sm"
				variant="ghost"
				onClick={onCancel}
				data-testid="link-cancel"
			>
				Cancel
			</Button>
		</form>
	);
}

// ---------------------------------------------------------------------------
// Toolbar Button
// ---------------------------------------------------------------------------

function ToolbarButton({
	onClick,
	isActive,
	disabled,
	icon: Icon,
	label,
	testId,
}: Readonly<{
	onClick: () => void;
	isActive?: boolean;
	disabled?: boolean;
	icon: React.ComponentType<{ className?: string }>;
	label: string;
	testId: string;
}>) {
	return (
		<Button
			type="button"
			variant="ghost"
			size="sm"
			onClick={onClick}
			disabled={disabled}
			className={isActive ? "bg-accent text-accent-foreground" : ""}
			aria-label={label}
			aria-pressed={isActive}
			data-testid={testId}
		>
			<Icon className="h-4 w-4" />
		</Button>
	);
}

// ---------------------------------------------------------------------------
// Toolbar Component
// ---------------------------------------------------------------------------

export function EditorToolbar({ editor }: Readonly<EditorToolbarProps>) {
	const [showLinkDialog, setShowLinkDialog] = useState(false);
	const [linkDialogUrl, setLinkDialogUrl] = useState("");

	const handleLinkSubmit = useCallback(
		(url: string) => {
			if (!editor) return;
			if (url) {
				editor
					.chain()
					.focus()
					.extendMarkRange("link")
					.setLink({ href: url })
					.run();
			} else {
				editor.chain().focus().extendMarkRange("link").unsetLink().run();
			}
			setShowLinkDialog(false);
		},
		[editor],
	);

	if (!editor) return null;

	return (
		<div
			className="border-border flex flex-wrap items-center gap-1 border-b p-1"
			role="toolbar"
			aria-label="Formatting toolbar"
			data-testid="editor-toolbar"
		>
			{/* Text style */}
			<div className="flex items-center gap-0.5">
				<ToolbarButton
					onClick={() => editor.chain().focus().toggleBold().run()}
					isActive={editor.isActive("bold")}
					icon={Bold}
					label="Bold"
					testId="toolbar-bold"
				/>
				<ToolbarButton
					onClick={() => editor.chain().focus().toggleItalic().run()}
					isActive={editor.isActive("italic")}
					icon={Italic}
					label="Italic"
					testId="toolbar-italic"
				/>
			</div>

			<div className="bg-border mx-1 h-6 w-px" role="separator" />

			{/* Headings */}
			<div className="flex items-center gap-0.5">
				<ToolbarButton
					onClick={() =>
						editor.chain().focus().toggleHeading({ level: 1 }).run()
					}
					isActive={editor.isActive("heading", { level: 1 })}
					icon={Heading1}
					label="Heading 1"
					testId="toolbar-h1"
				/>
				<ToolbarButton
					onClick={() =>
						editor.chain().focus().toggleHeading({ level: 2 }).run()
					}
					isActive={editor.isActive("heading", { level: 2 })}
					icon={Heading2}
					label="Heading 2"
					testId="toolbar-h2"
				/>
				<ToolbarButton
					onClick={() =>
						editor.chain().focus().toggleHeading({ level: 3 }).run()
					}
					isActive={editor.isActive("heading", { level: 3 })}
					icon={Heading3}
					label="Heading 3"
					testId="toolbar-h3"
				/>
				<ToolbarButton
					onClick={() =>
						editor.chain().focus().toggleHeading({ level: 4 }).run()
					}
					isActive={editor.isActive("heading", { level: 4 })}
					icon={Heading4}
					label="Heading 4"
					testId="toolbar-h4"
				/>
			</div>

			<div className="bg-border mx-1 h-6 w-px" role="separator" />

			{/* Lists */}
			<div className="flex items-center gap-0.5">
				<ToolbarButton
					onClick={() => editor.chain().focus().toggleBulletList().run()}
					isActive={editor.isActive("bulletList")}
					icon={List}
					label="Bullet list"
					testId="toolbar-bullet-list"
				/>
				<ToolbarButton
					onClick={() => editor.chain().focus().toggleOrderedList().run()}
					isActive={editor.isActive("orderedList")}
					icon={ListOrdered}
					label="Ordered list"
					testId="toolbar-ordered-list"
				/>
			</div>

			<div className="bg-border mx-1 h-6 w-px" role="separator" />

			{/* Insert */}
			<div className="flex items-center gap-0.5">
				<ToolbarButton
					onClick={() => editor.chain().focus().setHorizontalRule().run()}
					icon={Minus}
					label="Horizontal rule"
					testId="toolbar-hr"
				/>
				<ToolbarButton
					onClick={() => {
						setLinkDialogUrl(editor.getAttributes("link").href ?? "");
						setShowLinkDialog(true);
					}}
					isActive={editor.isActive("link")}
					icon={Link}
					label="Link"
					testId="toolbar-link"
				/>
			</div>

			<div className="bg-border mx-1 h-6 w-px" role="separator" />

			{/* History */}
			<div className="flex items-center gap-0.5">
				<ToolbarButton
					onClick={() => editor.chain().focus().undo().run()}
					disabled={!editor.can().undo()}
					icon={Undo}
					label="Undo"
					testId="toolbar-undo"
				/>
				<ToolbarButton
					onClick={() => editor.chain().focus().redo().run()}
					disabled={!editor.can().redo()}
					icon={Redo}
					label="Redo"
					testId="toolbar-redo"
				/>
			</div>

			{/* Link dialog */}
			{showLinkDialog && (
				<LinkDialog
					initialUrl={linkDialogUrl}
					onSubmit={handleLinkSubmit}
					onCancel={() => setShowLinkDialog(false)}
				/>
			)}
		</div>
	);
}

export type { EditorToolbarProps };
