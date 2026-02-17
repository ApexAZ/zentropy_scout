/**
 * Shared checkbox sections for resume content selection.
 *
 * REQ-012 §9.2: Renders hierarchical job/bullet checkboxes plus flat
 * education, certification, and skill checkbox lists. Used by both
 * the new-resume wizard and the resume detail editor.
 */

import { Checkbox } from "@/components/ui/checkbox";
import type { UseResumeContentSelectionReturn } from "@/hooks/use-resume-content-selection";
import type {
	Certification,
	Education,
	Skill,
	WorkHistory,
} from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ResumeContentCheckboxesProps {
	/** Work history entries to render as job checkboxes. */
	jobs: WorkHistory[];
	/** Education entries to render as checkboxes. */
	educations: Education[];
	/** Certification entries to render as checkboxes. */
	certifications: Certification[];
	/** Skill entries to render as checkboxes. */
	skills: Skill[];
	/** Selection state and handlers from useResumeContentSelection. */
	selection: UseResumeContentSelectionReturn;
	/**
	 * Optional render prop for bullet items within an included job.
	 * When provided, the consumer controls bullet rendering (e.g. for
	 * drag-and-drop reordering). When omitted, a simple static list
	 * is rendered.
	 */
	renderBullets?: (
		job: WorkHistory,
		selectedBullets: string[],
	) => React.ReactNode;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function ResumeContentCheckboxes({
	jobs,
	educations,
	certifications,
	skills,
	selection,
	renderBullets,
}: Readonly<ResumeContentCheckboxesProps>) {
	return (
		<>
			{/* Job inclusion checkboxes */}
			<div className="mb-8">
				<h2 className="mb-4 text-lg font-semibold">Included Jobs</h2>
				<div className="space-y-4">
					{jobs.map((job) => {
						const isIncluded = selection.includedJobs.includes(job.id);
						const selectedBullets = selection.bulletSelections[job.id] ?? [];

						return (
							<div key={job.id} className="space-y-2">
								<div className="flex items-center gap-2">
									<Checkbox
										id={`job-${job.id}`}
										checked={isIncluded}
										onCheckedChange={() =>
											selection.handleToggleJob(job.id, job)
										}
										aria-label={`${job.job_title} at ${job.company_name}`}
									/>
									<label
										htmlFor={`job-${job.id}`}
										className="cursor-pointer text-sm font-medium"
									>
										{job.job_title}
									</label>
									<span className="text-muted-foreground text-sm">
										{job.company_name}
									</span>
								</div>

								{isIncluded &&
									job.bullets.length > 0 &&
									(renderBullets ? (
										renderBullets(job, selectedBullets)
									) : (
										<div className="ml-6 space-y-1">
											{job.bullets.map((bullet) => (
												<div
													key={bullet.id}
													className="flex items-center gap-2"
												>
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
											))}
										</div>
									))}
							</div>
						);
					})}
				</div>
			</div>

			{/* Education checkboxes */}
			{educations.length > 0 && (
				<div className="mb-8">
					<h2 className="mb-4 text-lg font-semibold">Education</h2>
					<div className="space-y-2">
						{educations.map((edu) => (
							<div key={edu.id} className="flex items-center gap-2">
								<Checkbox
									id={`education-${edu.id}`}
									checked={selection.includedEducation.includes(edu.id)}
									onCheckedChange={() =>
										selection.handleToggleEducation(edu.id)
									}
									aria-label={`${edu.degree} ${edu.field_of_study} at ${edu.institution}`}
								/>
								<label
									htmlFor={`education-${edu.id}`}
									className="cursor-pointer text-sm"
								>
									{edu.degree} {edu.field_of_study} &mdash; {edu.institution}
								</label>
							</div>
						))}
					</div>
				</div>
			)}

			{/* Certification checkboxes */}
			{certifications.length > 0 && (
				<div className="mb-8">
					<h2 className="mb-4 text-lg font-semibold">Certifications</h2>
					<div className="space-y-2">
						{certifications.map((cert) => (
							<div key={cert.id} className="flex items-center gap-2">
								<Checkbox
									id={`certification-${cert.id}`}
									checked={selection.includedCertifications.includes(cert.id)}
									onCheckedChange={() =>
										selection.handleToggleCertification(cert.id)
									}
									aria-label={`${cert.certification_name} from ${cert.issuing_organization}`}
								/>
								<label
									htmlFor={`certification-${cert.id}`}
									className="cursor-pointer text-sm"
								>
									{cert.certification_name} &mdash; {cert.issuing_organization}
								</label>
							</div>
						))}
					</div>
				</div>
			)}

			{/* Skills emphasis checkboxes */}
			{skills.length > 0 && (
				<div className="mb-8">
					<h2 className="mb-4 text-lg font-semibold">Skills Emphasis</h2>
					<div className="flex flex-wrap gap-2">
						{skills.map((skill) => (
							<div
								key={skill.id}
								className="flex items-center gap-2 rounded-md border px-2 py-1"
							>
								<Checkbox
									id={`skill-${skill.id}`}
									checked={selection.skillsEmphasis.includes(skill.id)}
									onCheckedChange={() => selection.handleToggleSkill(skill.id)}
									aria-label={skill.skill_name}
								/>
								<label
									htmlFor={`skill-${skill.id}`}
									className="cursor-pointer text-sm"
								>
									{skill.skill_name}
								</label>
							</div>
						))}
					</div>
				</div>
			)}
		</>
	);
}

export { ResumeContentCheckboxes };
export type { ResumeContentCheckboxesProps };
