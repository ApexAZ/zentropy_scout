"use client";

/**
 * Resume upload step for onboarding wizard (Step 1).
 *
 * REQ-019 §7.2: Drag-and-drop or file picker for PDF upload,
 * client-side validation (10MB max), upload progress indicator,
 * skip option, and auto-advance on success. Calls the resume
 * parse endpoint to extract structured data for form pre-population.
 */

import { AlertCircle, CheckCircle2, FileUp, Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ApiError, apiUploadFile } from "@/lib/api-client";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { ResumeParseData } from "@/lib/onboarding-provider";
import { cn } from "@/lib/utils";
import type { ApiResponse } from "@/types/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Maximum allowed file size: 10 MB. */
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;

/** Human-readable size label. */
const MAX_FILE_SIZE_LABEL = "10MB";

/** Accepted file extensions (lowercase). PDF only — pdfplumber backend. */
const ACCEPTED_EXTENSIONS = new Set([".pdf"]);

/** Accepted MIME types (client-side hint, backend validates magic bytes). */
const ACCEPTED_MIME_TYPES = new Set(["application/pdf"]);

/** File input accept attribute value. */
const FILE_INPUT_ACCEPT = ".pdf";

/** Delay before auto-advancing after successful upload. */
const AUTO_ADVANCE_DELAY_MS = 1500;

/** Simulated progress increment interval. */
const PROGRESS_INTERVAL_MS = 300;

/** Simulated progress increment step. */
const PROGRESS_INCREMENT = 15;

/** Simulated progress cap (actual 100% set on completion). */
const PROGRESS_CAP = 90;

/** Initial simulated progress value when upload starts. */
const PROGRESS_INITIAL = 10;

/** Client-side validation message for non-PDF files. */
const PDF_ONLY_ERROR = "Only PDF files are accepted.";

/** Friendly error messages keyed by API error code. */
const FRIENDLY_ERROR_MESSAGES: Readonly<Record<string, string>> = {
	FILE_TOO_LARGE: `File must be ${MAX_FILE_SIZE_LABEL} or smaller.`,
	INVALID_FILE_CONTENT: PDF_ONLY_ERROR,
	VALIDATION_ERROR:
		"Couldn't read this PDF. You can skip this step and enter your info manually.",
	PDF_REQUIRED: "Only PDF files are supported for resume parsing.",
};

/** Fallback error message for unexpected errors. */
const GENERIC_ERROR_MESSAGE =
	"Couldn't read this PDF. You can skip this step and enter your info manually.";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type UploadStatus = "idle" | "uploading" | "success" | "error";

/** Extract the lowercase file extension from a file name. */
function getFileExtension(fileName: string): string {
	const dotIndex = fileName.lastIndexOf(".");
	return dotIndex >= 0 ? fileName.slice(dotIndex).toLowerCase() : "";
}

/** Validate file type (extension + MIME hint) and size. Returns error or null. */
function validateFile(file: File): string | null {
	const ext = getFileExtension(file.name);
	if (!ACCEPTED_EXTENSIONS.has(ext)) {
		return PDF_ONLY_ERROR;
	}
	if (file.type && !ACCEPTED_MIME_TYPES.has(file.type)) {
		return PDF_ONLY_ERROR;
	}
	if (file.size > MAX_FILE_SIZE_BYTES) {
		return `File must be ${MAX_FILE_SIZE_LABEL} or smaller.`;
	}
	return null;
}

/** Map an ApiError to a user-friendly message. */
function toFriendlyError(err: unknown): string {
	if (err instanceof ApiError) {
		return FRIENDLY_ERROR_MESSAGES[err.code] ?? GENERIC_ERROR_MESSAGE;
	}
	return GENERIC_ERROR_MESSAGE;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 1: Resume Upload.
 *
 * Renders a drag-and-drop zone (or click-to-browse) for PDF files.
 * Validates client-side before uploading via POST /onboarding/resume-parse.
 * Shows simulated progress, success message, then auto-advances.
 * Always offers a skip option for manual entry.
 */
export function ResumeUploadStep() {
	const { next, skip, setResumeParseData } = useOnboarding();

	const [status, setStatus] = useState<UploadStatus>("idle");
	const [error, setError] = useState<string | null>(null);
	const [progress, setProgress] = useState(0);
	const [isDragOver, setIsDragOver] = useState(false);

	const fileInputRef = useRef<HTMLInputElement>(null);
	const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
	const abortRef = useRef<AbortController | null>(null);

	// Cleanup timers and abort in-flight upload on unmount
	useEffect(() => {
		return () => {
			abortRef.current?.abort();
			if (timerRef.current !== null) clearTimeout(timerRef.current);
			if (intervalRef.current !== null) clearInterval(intervalRef.current);
		};
	}, []);

	// -----------------------------------------------------------------------
	// Upload handler
	// -----------------------------------------------------------------------

	const handleFile = useCallback(
		async (file: File) => {
			const validationError = validateFile(file);
			if (validationError) {
				setError(validationError);
				setStatus("error");
				return;
			}

			// Abort any previous in-flight upload and clear stale interval
			abortRef.current?.abort();
			if (intervalRef.current !== null) clearInterval(intervalRef.current);

			setStatus("uploading");
			setError(null);
			setProgress(PROGRESS_INITIAL);

			// Simulated progress: increment toward cap
			intervalRef.current = setInterval(() => {
				setProgress((prev) =>
					Math.min(prev + PROGRESS_INCREMENT, PROGRESS_CAP),
				);
			}, PROGRESS_INTERVAL_MS);

			const controller = new AbortController();
			abortRef.current = controller;

			try {
				const response = await apiUploadFile<ApiResponse<ResumeParseData>>(
					"/onboarding/resume-parse",
					file,
					undefined,
					{ signal: controller.signal },
				);

				setResumeParseData(response.data);

				if (intervalRef.current !== null) clearInterval(intervalRef.current);
				setProgress(100);
				setStatus("success");

				timerRef.current = setTimeout(() => {
					next();
				}, AUTO_ADVANCE_DELAY_MS);
			} catch (err) {
				if (intervalRef.current !== null) clearInterval(intervalRef.current);

				// Ignore abort errors (component unmounting or new upload started)
				if (controller.signal.aborted) return;

				setProgress(0);
				setStatus("error");
				setError(toFriendlyError(err));
			}
		},
		[next, setResumeParseData],
	);

	// -----------------------------------------------------------------------
	// Event handlers
	// -----------------------------------------------------------------------

	const handleDrop = useCallback(
		(e: React.DragEvent) => {
			e.preventDefault();
			setIsDragOver(false);
			const file = e.dataTransfer.files[0];
			if (file) {
				void handleFile(file);
			}
		},
		[handleFile],
	);

	const handleDragOverOrEnter = useCallback((e: React.DragEvent) => {
		e.preventDefault();
		setIsDragOver(true);
	}, []);

	const handleDragLeave = useCallback((e: React.DragEvent) => {
		e.preventDefault();
		setIsDragOver(false);
	}, []);

	const handleInputChange = useCallback(
		(e: React.ChangeEvent<HTMLInputElement>) => {
			const file = e.target.files?.[0];
			if (file) {
				void handleFile(file);
			}
		},
		[handleFile],
	);

	const handleRetry = useCallback(() => {
		setStatus("idle");
		setError(null);
		setProgress(0);
	}, []);

	const openFilePicker = useCallback(() => {
		fileInputRef.current?.click();
	}, []);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div className="flex flex-1 flex-col items-center justify-center gap-6">
			<p className="text-muted-foreground text-center text-lg">
				Got a resume? Upload it and I&apos;ll use it to pre-fill your profile.
			</p>

			{/* Hidden file input */}
			<input
				ref={fileInputRef}
				type="file"
				accept={FILE_INPUT_ACCEPT}
				className="hidden"
				onChange={handleInputChange}
				data-testid="file-input"
			/>

			{/* Idle: Drop zone */}
			{status === "idle" && (
				<button
					type="button"
					onClick={openFilePicker}
					onDrop={handleDrop}
					onDragOver={handleDragOverOrEnter}
					onDragEnter={handleDragOverOrEnter}
					onDragLeave={handleDragLeave}
					className={cn(
						"w-full max-w-md cursor-pointer rounded-lg border-2 border-dashed p-12 text-center transition-colors",
						isDragOver
							? "border-primary bg-primary/5"
							: "border-muted-foreground/25 hover:border-primary/50",
					)}
					data-testid="drop-zone"
				>
					<FileUp className="text-muted-foreground mx-auto mb-3 h-10 w-10" />
					<p className="font-medium">Drop PDF here</p>
					<p className="text-muted-foreground mt-1 text-sm">
						or click to browse
					</p>
					<p className="text-muted-foreground mt-3 text-xs">
						Max {MAX_FILE_SIZE_LABEL} &middot; PDF only
					</p>
				</button>
			)}

			{/* Uploading: Progress indicator */}
			{status === "uploading" && (
				<div
					className="w-full max-w-md text-center"
					data-testid="upload-progress"
				>
					<Loader2 className="text-primary mx-auto mb-3 h-8 w-8 animate-spin" />
					<p className="mb-3 font-medium">Parsing resume...</p>
					<Progress value={progress} />
				</div>
			)}

			{/* Success: Confirmation */}
			{status === "success" && (
				<div className="text-center" data-testid="upload-success">
					<CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-green-500" />
					<p className="font-medium">
						Resume parsed! I&apos;ll use this to pre-fill your profile.
					</p>
				</div>
			)}

			{/* Error: Message + retry */}
			{status === "error" && (
				<div className="text-center" data-testid="upload-error">
					<AlertCircle className="text-destructive mx-auto mb-3 h-10 w-10" />
					<p className="text-destructive font-medium">{error}</p>
					<Button variant="outline" onClick={handleRetry} className="mt-3">
						Try again
					</Button>
				</div>
			)}

			{/* Skip link (hidden during upload and success) */}
			{status !== "uploading" && status !== "success" && (
				<button
					type="button"
					onClick={skip}
					className="text-muted-foreground hover:text-foreground text-sm underline underline-offset-4 transition-colors"
				>
					Skip &mdash; I&apos;ll enter manually
				</button>
			)}
		</div>
	);
}
