/**
 * Persona reference panel for the resume editor.
 *
 * REQ-026 §5.1–§5.2: Collapsible sections showing Contact Info,
 * Work History, Education, Skills, and Certifications.
 * Click any item to copy its text to clipboard.
 */

import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Copy, Loader2 } from "lucide-react";

import { apiGet } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type {
	Certification,
	Education,
	Persona,
	Skill,
	WorkHistory,
} from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PersonaReferencePanelProps {
	personaId: string;
}

const EMPTY_TEXT_CLASS = "text-muted-foreground text-xs italic";

// ---------------------------------------------------------------------------
// CollapsibleSection
// ---------------------------------------------------------------------------

function CollapsibleSection({
	title,
	testId,
	defaultOpen = true,
	children,
}: Readonly<{
	title: string;
	testId: string;
	defaultOpen?: boolean;
	children: React.ReactNode;
}>) {
	const [isOpen, setIsOpen] = useState(defaultOpen);

	return (
		<div data-testid={testId}>
			<button
				type="button"
				onClick={() => setIsOpen((prev) => !prev)}
				aria-expanded={isOpen}
				className="hover:bg-muted focus-visible:ring-ring/50 flex w-full items-center gap-1 rounded px-1 py-1.5 text-left text-sm font-semibold focus-visible:ring-[3px] focus-visible:outline-none"
			>
				{isOpen ? (
					<ChevronDown className="h-4 w-4 shrink-0" />
				) : (
					<ChevronRight className="h-4 w-4 shrink-0" />
				)}
				{title}
			</button>
			{isOpen && <div className="space-y-1 py-1 pl-5">{children}</div>}
		</div>
	);
}

// ---------------------------------------------------------------------------
// CopyableItem
// ---------------------------------------------------------------------------

function CopyableItem({
	text,
	label,
}: Readonly<{ text: string; label?: string }>) {
	const displayLabel = label ?? text;

	const handleCopy = useCallback(async () => {
		try {
			await navigator.clipboard.writeText(text);
			showToast.success("Copied to clipboard");
		} catch {
			showToast.error("Failed to copy to clipboard");
		}
	}, [text]);

	return (
		<button
			type="button"
			onClick={handleCopy}
			aria-label={`Copy ${text}`}
			className="text-muted-foreground hover:bg-muted hover:text-foreground group focus-visible:ring-ring/50 flex w-full items-center gap-1.5 rounded px-1 py-0.5 text-left text-sm focus-visible:ring-[3px] focus-visible:outline-none"
		>
			<Copy className="h-3 w-3 shrink-0 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100" />
			<span className="truncate">{displayLabel}</span>
		</button>
	);
}

// ---------------------------------------------------------------------------
// JobEntry (expandable per job)
// ---------------------------------------------------------------------------

function JobEntry({ job }: Readonly<{ job: WorkHistory }>) {
	const [isOpen, setIsOpen] = useState(false);
	const dateRange = job.is_current
		? `${job.start_date.slice(0, 4)} – Present`
		: `${job.start_date.slice(0, 4)} – ${job.end_date?.slice(0, 4) ?? ""}`;
	const label = `${job.job_title} — ${job.company_name} (${dateRange})`;

	return (
		<div>
			<button
				type="button"
				onClick={() => setIsOpen((prev) => !prev)}
				aria-expanded={isOpen}
				aria-label={label}
				className="hover:bg-muted focus-visible:ring-ring/50 flex w-full items-center gap-1 rounded px-1 py-0.5 text-left text-sm focus-visible:ring-[3px] focus-visible:outline-none"
			>
				{isOpen ? (
					<ChevronDown className="h-3 w-3 shrink-0" />
				) : (
					<ChevronRight className="h-3 w-3 shrink-0" />
				)}
				<span className="truncate font-medium">
					{job.job_title} — {job.company_name}
				</span>
			</button>
			{isOpen && (
				<div className="space-y-0.5 py-1 pl-5">
					<p className="text-muted-foreground text-xs">{dateRange}</p>
					{job.bullets.length > 0 ? (
						job.bullets.map((bullet) => (
							<CopyableItem key={bullet.id} text={bullet.text} />
						))
					) : (
						<p className={EMPTY_TEXT_CLASS}>No bullets</p>
					)}
				</div>
			)}
		</div>
	);
}

// ---------------------------------------------------------------------------
// PersonaReferencePanel
// ---------------------------------------------------------------------------

export function PersonaReferencePanel({
	personaId,
}: Readonly<PersonaReferencePanelProps>) {
	const { data: personaData, isLoading: personaLoading } = useQuery({
		queryKey: queryKeys.persona(personaId),
		queryFn: () => apiGet<ApiResponse<Persona>>(`/personas/${personaId}`),
	});

	const { data: workHistoryData, isLoading: whLoading } = useQuery({
		queryKey: queryKeys.workHistory(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<WorkHistory>>(
				`/personas/${personaId}/work-history`,
			),
	});

	const { data: educationData, isLoading: eduLoading } = useQuery({
		queryKey: queryKeys.education(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<Education>>(`/personas/${personaId}/education`),
	});

	const { data: skillData, isLoading: skillLoading } = useQuery({
		queryKey: queryKeys.skills(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<Skill>>(`/personas/${personaId}/skills`),
	});

	const { data: certData, isLoading: certLoading } = useQuery({
		queryKey: queryKeys.certifications(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<Certification>>(
				`/personas/${personaId}/certifications`,
			),
	});

	const isLoading =
		personaLoading || whLoading || eduLoading || skillLoading || certLoading;

	if (isLoading) {
		return (
			<div
				data-testid="persona-panel-loading"
				className="flex items-center justify-center py-8"
			>
				<Loader2 className="text-muted-foreground h-5 w-5 animate-spin" />
			</div>
		);
	}

	const persona = personaData?.data;
	const workHistories = workHistoryData?.data ?? [];
	const educations = educationData?.data ?? [];
	const skills = skillData?.data ?? [];
	const certifications = certData?.data ?? [];

	const location = persona
		? [persona.home_city, persona.home_state, persona.home_country]
				.filter(Boolean)
				.join(", ")
		: "";

	return (
		<div
			data-testid="persona-reference-panel"
			className="space-y-2 overflow-y-auto text-sm"
		>
			<h3 className="px-1 text-xs font-semibold tracking-wide uppercase">
				Persona Reference
			</h3>

			{/* Contact Info */}
			<CollapsibleSection title="Contact Info" testId="section-contact-info">
				{persona ? (
					<>
						<CopyableItem text={persona.full_name} />
						<CopyableItem text={persona.email} />
						<CopyableItem text={persona.phone} />
						{location && <CopyableItem text={location} />}
					</>
				) : (
					<p className={EMPTY_TEXT_CLASS}>No contact info</p>
				)}
			</CollapsibleSection>

			{/* Work History */}
			<CollapsibleSection title="Work History" testId="section-work-history">
				{workHistories.length > 0 ? (
					workHistories.map((job) => <JobEntry key={job.id} job={job} />)
				) : (
					<p className={EMPTY_TEXT_CLASS}>No work history</p>
				)}
			</CollapsibleSection>

			{/* Education */}
			<CollapsibleSection title="Education" testId="section-education">
				{educations.length > 0 ? (
					educations.map((edu) => (
						<CopyableItem
							key={edu.id}
							text={`${edu.degree} ${edu.field_of_study}, ${edu.institution}, ${edu.graduation_year}`}
						/>
					))
				) : (
					<p className={EMPTY_TEXT_CLASS}>No education</p>
				)}
			</CollapsibleSection>

			{/* Skills */}
			<CollapsibleSection title="Skills" testId="section-skills">
				{skills.length > 0 ? (
					<div className="flex flex-wrap gap-1">
						{skills.map((skill) => (
							<CopyableItem key={skill.id} text={skill.skill_name} />
						))}
					</div>
				) : (
					<p className={EMPTY_TEXT_CLASS}>No skills</p>
				)}
			</CollapsibleSection>

			{/* Certifications */}
			<CollapsibleSection
				title="Certifications"
				testId="section-certifications"
			>
				{certifications.length > 0 ? (
					certifications.map((cert) => (
						<CopyableItem
							key={cert.id}
							text={cert.certification_name}
							label={`${cert.certification_name} — ${cert.issuing_organization}`}
						/>
					))
				) : (
					<p className={EMPTY_TEXT_CLASS}>No certifications</p>
				)}
			</CollapsibleSection>
		</div>
	);
}
