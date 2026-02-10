import * as React from "react";
import { Download, Maximize, Minimize, ZoomIn, ZoomOut } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const ZOOM_MIN = 50;
const ZOOM_MAX = 200;
const ZOOM_STEP = 25;
const ZOOM_DEFAULT = 100;
const ALLOWED_PROTOCOLS = new Set(["https:", "http:", "blob:"]);

interface PdfViewerProps extends React.ComponentProps<"div"> {
	/** PDF source: Blob (component manages blob URL lifecycle) or string URL. */
	src: Blob | string;
	/** File name for the download button's `download` attribute. */
	fileName: string;
}

function sanitizeFileName(name: string): string {
	return name.replace(/[/\\]/g, "_").slice(0, 255);
}

function isAllowedUrl(url: string): boolean {
	try {
		const parsed = new URL(url, window.location.origin);
		return ALLOWED_PROTOCOLS.has(parsed.protocol);
	} catch {
		return false;
	}
}

function PdfViewer({ src, fileName, className, ...props }: PdfViewerProps) {
	const containerRef = React.useRef<HTMLDivElement>(null);
	const iframeRef = React.useRef<HTMLIFrameElement>(null);
	const [iframeSrc, setIframeSrc] = React.useState("");
	const [zoom, setZoom] = React.useState(ZOOM_DEFAULT);
	const [hasError, setHasError] = React.useState(false);
	const [isFullscreen, setIsFullscreen] = React.useState(false);

	const safeFileName = sanitizeFileName(fileName);

	// Blob URL lifecycle with validation (reset error first, then validate)
	React.useEffect(() => {
		setHasError(false);

		if (src instanceof Blob) {
			if (src.type !== "application/pdf") {
				setHasError(true);
				return;
			}
			const url = URL.createObjectURL(src);
			setIframeSrc(url);
			return () => URL.revokeObjectURL(url);
		}
		if (typeof src === "string" && isAllowedUrl(src)) {
			setIframeSrc(src);
		} else if (typeof src === "string") {
			setHasError(true);
		}
	}, [src]);

	// Iframe error listener (ref-based for reliable cross-browser support)
	React.useEffect(() => {
		const iframe = iframeRef.current;
		if (!iframe) return;

		function handleError() {
			setHasError(true);
		}

		iframe.addEventListener("error", handleError);
		return () => iframe.removeEventListener("error", handleError);
	}, [iframeSrc]);

	// Fullscreen change listener
	React.useEffect(() => {
		function handleFullscreenChange() {
			setIsFullscreen(document.fullscreenElement !== null);
		}

		document.addEventListener("fullscreenchange", handleFullscreenChange);
		return () =>
			document.removeEventListener("fullscreenchange", handleFullscreenChange);
	}, []);

	function handleZoomIn() {
		setZoom((prev) => Math.min(prev + ZOOM_STEP, ZOOM_MAX));
	}

	function handleZoomOut() {
		setZoom((prev) => Math.max(prev - ZOOM_STEP, ZOOM_MIN));
	}

	function handleDownload() {
		const anchor = document.createElement("a");
		anchor.href = iframeSrc;
		anchor.download = safeFileName;
		document.body.appendChild(anchor);
		anchor.click();
		document.body.removeChild(anchor);
	}

	function toggleFullscreen() {
		if (document.fullscreenElement) {
			document.exitFullscreen();
		} else {
			containerRef.current?.requestFullscreen();
		}
	}

	return (
		<div
			ref={containerRef}
			data-slot="pdf-viewer"
			className={cn("flex h-full flex-col", className)}
			{...props}
		>
			{hasError ? (
				<div
					role="alert"
					className="flex flex-col items-center justify-center gap-4 py-12 text-center"
				>
					<p className="text-lg font-semibold">Unable to preview this PDF.</p>
					<Button variant="outline" size="sm" asChild>
						<a href={iframeSrc} download={safeFileName}>
							Download File
						</a>
					</Button>
				</div>
			) : (
				<>
					<div
						role="toolbar"
						aria-label="PDF viewer controls"
						className="flex items-center justify-between border-b px-2 py-1"
					>
						<div className="flex items-center gap-1">
							<Button
								variant="ghost"
								size="icon-xs"
								aria-label="Zoom out"
								disabled={zoom <= ZOOM_MIN}
								onClick={handleZoomOut}
							>
								<ZoomOut />
							</Button>
							<span aria-live="polite" className="min-w-12 text-center text-sm">
								{zoom}%
							</span>
							<Button
								variant="ghost"
								size="icon-xs"
								aria-label="Zoom in"
								disabled={zoom >= ZOOM_MAX}
								onClick={handleZoomIn}
							>
								<ZoomIn />
							</Button>
						</div>
						<div className="flex items-center gap-1">
							<Button
								variant="ghost"
								size="icon-xs"
								aria-label="Download PDF"
								onClick={handleDownload}
							>
								<Download />
							</Button>
							<Button
								variant="ghost"
								size="icon-xs"
								aria-label={
									isFullscreen ? "Exit full screen" : "Enter full screen"
								}
								onClick={toggleFullscreen}
							>
								{isFullscreen ? <Minimize /> : <Maximize />}
							</Button>
						</div>
					</div>
					<div className="flex-1 overflow-auto">
						<div
							style={{
								transform: `scale(${zoom / 100})`,
								transformOrigin: "top left",
								width: `${10000 / zoom}%`,
							}}
							className="h-full"
						>
							<iframe
								ref={iframeRef}
								src={iframeSrc}
								title={`PDF preview: ${safeFileName}`}
								sandbox="allow-same-origin"
								referrerPolicy="no-referrer"
								className="h-full w-full border-0"
							/>
						</div>
					</div>
				</>
			)}
		</div>
	);
}

export { PdfViewer };
export type { PdfViewerProps };
