"use client";

/**
 * Export buttons for downloading resume or variant as PDF or DOCX.
 *
 * REQ-026 §6.2, REQ-027 §4.5: Action buttons include export options.
 */

import { Download, FileText } from "lucide-react";

import { buildUrl } from "@/lib/api-client";
import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ExportButtons({
	exportBasePath,
}: Readonly<{ exportBasePath: string }>) {
	return (
		<>
			<Button
				variant="outline"
				onClick={() =>
					window.open(
						buildUrl(`${exportBasePath}/export/pdf`),
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
						buildUrl(`${exportBasePath}/export/docx`),
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
