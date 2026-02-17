/**
 * Shared hook for resume content selection state management.
 *
 * REQ-012 §9.2: Manages checkbox state (included jobs, bullet selections,
 * bullet order, education, certifications, skills emphasis) and toggle
 * handlers used by both the new-resume wizard and the resume detail editor.
 */

import { useCallback, useState } from "react";

import type { WorkHistory } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ResumeContentSelectionState {
	includedJobs: string[];
	bulletSelections: Record<string, string[]>;
	bulletOrder: Record<string, string[]>;
	includedEducation: string[];
	includedCertifications: string[];
	skillsEmphasis: string[];
}

interface UseResumeContentSelectionReturn extends ResumeContentSelectionState {
	setIncludedJobs: React.Dispatch<React.SetStateAction<string[]>>;
	setBulletSelections: React.Dispatch<
		React.SetStateAction<Record<string, string[]>>
	>;
	setBulletOrder: React.Dispatch<
		React.SetStateAction<Record<string, string[]>>
	>;
	setIncludedEducation: React.Dispatch<React.SetStateAction<string[]>>;
	setIncludedCertifications: React.Dispatch<React.SetStateAction<string[]>>;
	setSkillsEmphasis: React.Dispatch<React.SetStateAction<string[]>>;
	handleToggleJob: (jobId: string, job: WorkHistory) => void;
	handleToggleBullet: (jobId: string, bulletId: string) => void;
	handleToggleEducation: (eduId: string) => void;
	handleToggleCertification: (certId: string) => void;
	handleToggleSkill: (skillId: string) => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

function useResumeContentSelection(): UseResumeContentSelectionReturn {
	const [includedJobs, setIncludedJobs] = useState<string[]>([]);
	const [bulletSelections, setBulletSelections] = useState<
		Record<string, string[]>
	>({});
	const [bulletOrder, setBulletOrder] = useState<Record<string, string[]>>({});
	const [includedEducation, setIncludedEducation] = useState<string[]>([]);
	const [includedCertifications, setIncludedCertifications] = useState<
		string[]
	>([]);
	const [skillsEmphasis, setSkillsEmphasis] = useState<string[]>([]);

	const handleToggleJob = useCallback((jobId: string, job: WorkHistory) => {
		setIncludedJobs((prev) => {
			if (prev.includes(jobId)) {
				setBulletSelections((bs) => {
					const next = { ...bs };
					delete next[jobId];
					return next;
				});
				setBulletOrder((bo) => {
					const next = { ...bo };
					delete next[jobId];
					return next;
				});
				return prev.filter((id) => id !== jobId);
			}
			const allBulletIds = job.bullets.map((b) => b.id);
			setBulletSelections((bs) => ({
				...bs,
				[jobId]: allBulletIds,
			}));
			setBulletOrder((bo) => ({
				...bo,
				[jobId]: allBulletIds,
			}));
			return [...prev, jobId];
		});
	}, []);

	const handleToggleBullet = useCallback((jobId: string, bulletId: string) => {
		setBulletSelections((prev) => {
			const current = prev[jobId] ?? [];
			const next = current.includes(bulletId)
				? current.filter((id) => id !== bulletId)
				: [...current, bulletId];
			return { ...prev, [jobId]: next };
		});
	}, []);

	const handleToggleEducation = useCallback((eduId: string) => {
		setIncludedEducation((prev) =>
			prev.includes(eduId)
				? prev.filter((id) => id !== eduId)
				: [...prev, eduId],
		);
	}, []);

	const handleToggleCertification = useCallback((certId: string) => {
		setIncludedCertifications((prev) =>
			prev.includes(certId)
				? prev.filter((id) => id !== certId)
				: [...prev, certId],
		);
	}, []);

	const handleToggleSkill = useCallback((skillId: string) => {
		setSkillsEmphasis((prev) =>
			prev.includes(skillId)
				? prev.filter((id) => id !== skillId)
				: [...prev, skillId],
		);
	}, []);

	return {
		includedJobs,
		bulletSelections,
		bulletOrder,
		includedEducation,
		includedCertifications,
		skillsEmphasis,
		setIncludedJobs,
		setBulletSelections,
		setBulletOrder,
		setIncludedEducation,
		setIncludedCertifications,
		setSkillsEmphasis,
		handleToggleJob,
		handleToggleBullet,
		handleToggleEducation,
		handleToggleCertification,
		handleToggleSkill,
	};
}

export { useResumeContentSelection };
export type { ResumeContentSelectionState, UseResumeContentSelectionReturn };
