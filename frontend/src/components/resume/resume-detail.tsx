"use client";

/**
 * Resume detail page with toggle view (Preview/Edit) and content
 * selection checkboxes.
 *
 * REQ-012 §9.2: Base resume editor with content selection.
 * REQ-026 §6.1–§6.3: Toggle view delegated to ResumeContentView.
 */

import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

import { buildUrl } from "@/lib/api-client";
import { orderBullets } from "@/lib/resume-helpers";
import { useResumeDetail } from "@/hooks/use-resume-detail";
import { ResumeContentCheckboxes } from "@/components/resume/resume-content-checkboxes";
import { ResumeContentView } from "@/components/resume/resume-content-view";
import { VariantsList } from "@/components/resume/variants-list";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { FailedState } from "@/components/ui/error-states";
import { PdfViewer } from "@/components/ui/pdf-viewer";
import { ReorderableList } from "@/components/ui/reorderable-list";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_SUMMARY_LENGTH = 5000;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ResumeDetailProps {
	resumeId: string;
	personaId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ResumeDetail({
	resumeId,
	personaId,
}: Readonly<ResumeDetailProps>) {
	const {
		isLoading,
		resumeError,
		refetchResume,
		resume,
		jobs,
		educations,
		certifications,
		skills,
		summary,
		setSummary,
		selection,
		isSaving,
		isRendering,
		handleSave,
		handleRenderPdf,
		handleReorderBullets,
	} = useResumeDetail({ resumeId, personaId });

	// -----------------------------------------------------------------------
	// Render states
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div data-testid="loading-spinner" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (resumeError) {
		return <FailedState onRetry={() => refetchResume()} />;
	}

	if (!resume) return null;

	const needsRender =
		!resume.rendered_at || resume.updated_at > resume.rendered_at;
	const renderButtonLabel = resume.rendered_at ? "Re-render PDF" : "Render PDF";
	const downloadUrl = buildUrl(`/base-resumes/${resumeId}/download`);

	// -----------------------------------------------------------------------
	// Main render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="resume-detail">
			{/* Header */}
			<div className="mb-6">
				<Link
					href="/resumes"
					aria-label="Back to Resumes"
					className="text-muted-foreground hover:text-foreground mb-2 inline-flex items-center gap-1 text-sm"
				>
					<ArrowLeft className="h-4 w-4" />
					Back to Resumes
				</Link>
				<div className="flex items-center gap-2">
					<h1 className="text-2xl font-bold">{resume.name}</h1>
					<span
						aria-label={`Status: ${resume.status}`}
						className="bg-muted rounded px-2 py-0.5 text-xs font-medium"
					>
						{resume.status}
					</span>
				</div>
				<p className="text-muted-foreground text-sm">{resume.role_type}</p>
			</div>

			{/* Toggle view: Preview/Edit or No-content prompt */}
			<ResumeContentView
				resumeId={resumeId}
				personaId={personaId}
				markdownContent={resume.markdown_content ?? null}
			/>

			{/* Summary editor */}
			<div className="mb-8">
				<label
					htmlFor="resume-summary"
					className="mb-2 block text-sm font-medium"
				>
					Summary
				</label>
				<textarea
					id="resume-summary"
					value={summary}
					onChange={(e) => setSummary(e.target.value)}
					rows={5}
					maxLength={MAX_SUMMARY_LENGTH}
					className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm"
				/>
			</div>

			{/* Content selection checkboxes */}
			<ResumeContentCheckboxes
				jobs={jobs}
				educations={educations}
				certifications={certifications}
				skills={skills}
				selection={selection}
				renderBullets={(job, selectedBullets) => (
					<div className="ml-6">
						<ReorderableList
							items={orderBullets(job.bullets, selection.bulletOrder[job.id])}
							onReorder={(reordered) => handleReorderBullets(job.id, reordered)}
							label={`Bullets for ${job.job_title}`}
							renderItem={(bullet, dragHandle) => (
								<div className="flex items-center gap-2">
									{dragHandle}
									<Checkbox
										id={`bullet-${bullet.id}`}
										checked={selectedBullets.includes(bullet.id)}
										onCheckedChange={() =>
											selection.handleToggleBullet(job.id, bullet.id)
										}
										aria-label={bullet.text}
									/>
									<label
										htmlFor={`bullet-${bullet.id}`}
										className="text-muted-foreground cursor-pointer text-sm"
									>
										{bullet.text}
									</label>
								</div>
							)}
						/>
					</div>
				)}
			/>

			{/* Actions */}
			<div className="flex items-center gap-2">
				<Button onClick={handleSave} disabled={isSaving}>
					{isSaving ? (
						<>
							<Loader2 className="mr-1 h-4 w-4 animate-spin" />
							Saving...
						</>
					) : (
						"Save"
					)}
				</Button>
				{needsRender && (
					<Button
						variant="outline"
						onClick={handleRenderPdf}
						disabled={isRendering}
					>
						{isRendering ? (
							<>
								<Loader2 className="mr-1 h-4 w-4 animate-spin" />
								Rendering...
							</>
						) : (
							renderButtonLabel
						)}
					</Button>
				)}
			</div>

			{/* PDF preview */}
			{resume.rendered_at && (
				<div className="mt-8">
					<h2 className="mb-4 text-lg font-semibold">PDF Preview</h2>
					<div className="h-[600px] rounded-md border">
						<PdfViewer src={downloadUrl} fileName={`${resume.name}.pdf`} />
					</div>
				</div>
			)}

			{/* Job Variants */}
			<div className="mt-8">
				<VariantsList baseResumeId={resumeId} />
			</div>
		</div>
	);
}
