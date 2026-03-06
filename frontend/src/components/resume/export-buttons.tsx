"use client";

/**
 * Export buttons for downloading resume as PDF or DOCX.
 *
 * REQ-026 §6.2: Action buttons per mode include export options.
 */

import { Download, FileText } from "lucide-react";

import { buildUrl } from "@/lib/api-client";
import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ExportButtons({ resumeId }: Readonly<{ resumeId: string }>) {
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
				<Download className="mr-1 h-4 w-4" />
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
				<FileText className="mr-1 h-4 w-4" />
				Export DOCX
			</Button>
		</>
	);
}
