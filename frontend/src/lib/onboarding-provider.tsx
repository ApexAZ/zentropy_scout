"use client";

/**
 * Onboarding state provider.
 *
 * REQ-012 §6.4: Checkpoint/resume behavior.
 * Manages current step, persisted step position, and resume prompts.
 *
 * Must be rendered inside a QueryClientProvider.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useMemo,
	useReducer,
	useRef,
	type ReactNode,
} from "react";

import {
	getStepByKey,
	getStepByNumber,
	TOTAL_STEPS,
} from "@/components/onboarding/onboarding-steps";
import type { ApiListResponse } from "@/types/api";
import type { Persona } from "@/types/persona";

import { apiGet, apiPatch, apiPost } from "./api-client";
import { queryKeys } from "./query-keys";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Checkpoint TTL: 24 hours in milliseconds. */
export const CHECKPOINT_TTL_MS = 24 * 60 * 60 * 1000;

/** UUID v4 format pattern for persona ID validation (defense-in-depth). */
const UUID_PATTERN =
	/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Validate that a string looks like a UUID before using it in URLs. */
function isValidUUID(value: string): boolean {
	return UUID_PATTERN.test(value);
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

/** Type of resume prompt to show on return. */
export type ResumePromptType = "welcome-back" | "expired";

interface OnboardingState {
	/** Current step number (1-12). Defaults to 1. */
	currentStep: number;
	/** Persona ID for PATCH calls. Null until persona is created/loaded. */
	personaId: string | null;
	/** Whether the initial checkpoint is being loaded from the server. */
	isLoadingCheckpoint: boolean;
	/** Whether a checkpoint is being saved to the server. */
	isSavingCheckpoint: boolean;
	/** Whether onboarding completion is in progress. */
	isCompleting: boolean;
	/** Resume prompt to display. Null if no prompt needed. */
	resumePrompt: ResumePromptType | null;
}

const initialState: OnboardingState = {
	currentStep: 1,
	personaId: null,
	isLoadingCheckpoint: true,
	isSavingCheckpoint: false,
	isCompleting: false,
	resumePrompt: null,
};

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

type OnboardingAction =
	| {
			type: "INIT";
			step: number;
			personaId: string | null;
			resumePrompt: ResumePromptType | null;
	  }
	| { type: "SET_STEP"; step: number }
	| { type: "SET_PERSONA_ID"; personaId: string }
	| { type: "SET_SAVING_CHECKPOINT"; saving: boolean }
	| { type: "SET_COMPLETING"; completing: boolean }
	| { type: "DISMISS_RESUME_PROMPT" };

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------

function onboardingReducer(
	state: OnboardingState,
	action: OnboardingAction,
): OnboardingState {
	switch (action.type) {
		case "INIT":
			return {
				...state,
				currentStep: action.step,
				personaId: action.personaId,
				isLoadingCheckpoint: false,
				resumePrompt: action.resumePrompt,
			};

		case "SET_STEP": {
			const clamped = Math.min(Math.max(action.step, 1), TOTAL_STEPS);
			return { ...state, currentStep: clamped };
		}

		case "SET_PERSONA_ID":
			return { ...state, personaId: action.personaId };

		case "SET_SAVING_CHECKPOINT":
			return { ...state, isSavingCheckpoint: action.saving };

		case "SET_COMPLETING":
			return { ...state, isCompleting: action.completing };

		case "DISMISS_RESUME_PROMPT":
			return { ...state, resumePrompt: null };

		default:
			return state;
	}
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface OnboardingContextValue {
	/** Current step number (1-12). */
	currentStep: number;
	/** Total number of steps (always 12). */
	totalSteps: number;
	/** Human-readable name of the current step. */
	stepName: string;
	/** Whether the current step can be skipped. */
	isStepSkippable: boolean;
	/** Persona ID. Null until persona is created/loaded. */
	personaId: string | null;
	/** Whether the initial checkpoint is being loaded. */
	isLoadingCheckpoint: boolean;
	/** Whether a checkpoint save is in progress. */
	isSavingCheckpoint: boolean;
	/** Whether onboarding completion is in progress. */
	isCompleting: boolean;
	/** Resume prompt type to display. Null if none. */
	resumePrompt: ResumePromptType | null;
	/** Complete onboarding: PATCH persona, trigger Scouter, invalidate cache. */
	completeOnboarding: () => Promise<void>;
	/** Advance to the next step and save checkpoint. */
	next: () => void;
	/** Go back to the previous step and save checkpoint. */
	back: () => void;
	/** Skip the current step and advance. */
	skip: () => void;
	/** Navigate directly to a specific step. */
	goToStep: (step: number) => void;
	/** Restart onboarding from step 1. */
	restart: () => void;
	/** Dismiss the resume prompt. */
	dismissResumePrompt: () => void;
	/** Update the persona ID (called when persona is created). */
	setPersonaId: (id: string) => void;
}

const OnboardingContext = createContext<OnboardingContextValue | null>(null);

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Access onboarding state and navigation actions.
 *
 * Must be called within an OnboardingProvider.
 *
 * @returns Object with step state, navigation actions, and checkpoint status.
 * @throws Error if called outside an OnboardingProvider.
 */
export function useOnboarding(): OnboardingContextValue {
	const ctx = useContext(OnboardingContext);
	if (!ctx) {
		throw new Error("useOnboarding must be used within an OnboardingProvider");
	}
	return ctx;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface OnboardingProviderProps {
	children: ReactNode;
}

/**
 * Manages onboarding wizard state: current step, checkpoint persistence,
 * and resume prompts.
 *
 * On mount, fetches the persona to determine the starting step. If the
 * user was previously mid-onboarding, shows a resume prompt. Checkpoint
 * position is saved to the server on every navigation action.
 *
 * @param props.children - React children to render.
 */
export function OnboardingProvider({
	children,
}: Readonly<OnboardingProviderProps>) {
	const { data, isLoading: isQueryLoading } = useQuery({
		queryKey: queryKeys.personas,
		queryFn: () => apiGet<ApiListResponse<Persona>>("/personas"),
	});

	const [state, dispatch] = useReducer(onboardingReducer, initialState);

	// Refs for stable callback closures
	const personaIdRef = useRef<string | null>(state.personaId);
	const currentStepRef = useRef(state.currentStep);
	const isInitializedRef = useRef(false);
	const saveCounterRef = useRef(0);

	useEffect(() => {
		personaIdRef.current = state.personaId;
	}, [state.personaId]);

	useEffect(() => {
		currentStepRef.current = state.currentStep;
	}, [state.currentStep]);

	// -----------------------------------------------------------------------
	// Initialize from server checkpoint
	// -----------------------------------------------------------------------

	useEffect(() => {
		if (isQueryLoading || isInitializedRef.current) return;
		isInitializedRef.current = true;

		const persona = data?.data[0];

		if (!persona) {
			dispatch({
				type: "INIT",
				step: 1,
				personaId: null,
				resumePrompt: null,
			});
			return;
		}

		if (!persona.onboarding_step) {
			dispatch({
				type: "INIT",
				step: 1,
				personaId: persona.id,
				resumePrompt: null,
			});
			return;
		}

		const stepDef = getStepByKey(persona.onboarding_step);
		const step = stepDef?.number ?? 1;

		const updatedAt = new Date(persona.updated_at).getTime();
		const elapsed = Date.now() - updatedAt;
		const expired = elapsed > CHECKPOINT_TTL_MS;

		dispatch({
			type: "INIT",
			step,
			personaId: persona.id,
			resumePrompt: expired ? "expired" : "welcome-back",
		});
	}, [data, isQueryLoading]);

	// -----------------------------------------------------------------------
	// Checkpoint persistence
	// -----------------------------------------------------------------------

	const saveCheckpoint = useCallback(async (step: number) => {
		const pid = personaIdRef.current;
		if (!pid || !isValidUUID(pid)) return;

		const stepDef = getStepByNumber(step);
		if (!stepDef) return;

		const saveId = ++saveCounterRef.current;
		dispatch({ type: "SET_SAVING_CHECKPOINT", saving: true });
		try {
			await apiPatch(`/personas/${pid}`, {
				onboarding_step: stepDef.key,
			});
		} catch {
			// Checkpoint save failed — silent failure, user can still navigate
		} finally {
			// Only clear saving flag if this is still the latest save
			if (saveCounterRef.current === saveId) {
				dispatch({ type: "SET_SAVING_CHECKPOINT", saving: false });
			}
		}
	}, []);

	// -----------------------------------------------------------------------
	// Navigation actions
	// -----------------------------------------------------------------------

	const next = useCallback(() => {
		const step = currentStepRef.current;
		if (step >= TOTAL_STEPS) return;
		const nextStep = step + 1;
		dispatch({ type: "SET_STEP", step: nextStep });
		void saveCheckpoint(nextStep);
	}, [saveCheckpoint]);

	const back = useCallback(() => {
		const step = currentStepRef.current;
		if (step <= 1) return;
		const prevStep = step - 1;
		dispatch({ type: "SET_STEP", step: prevStep });
		void saveCheckpoint(prevStep);
	}, [saveCheckpoint]);

	const skip = useCallback(() => {
		const step = currentStepRef.current;
		if (step >= TOTAL_STEPS) return;
		const nextStep = step + 1;
		dispatch({ type: "SET_STEP", step: nextStep });
		void saveCheckpoint(nextStep);
	}, [saveCheckpoint]);

	const goToStep = useCallback(
		(step: number) => {
			dispatch({ type: "SET_STEP", step });
			void saveCheckpoint(step);
		},
		[saveCheckpoint],
	);

	const restart = useCallback(() => {
		dispatch({ type: "SET_STEP", step: 1 });
		void saveCheckpoint(1);
	}, [saveCheckpoint]);

	const dismissResumePrompt = useCallback(() => {
		dispatch({ type: "DISMISS_RESUME_PROMPT" });
	}, []);

	const setPersonaId = useCallback((id: string) => {
		if (!isValidUUID(id)) return;
		personaIdRef.current = id;
		dispatch({ type: "SET_PERSONA_ID", personaId: id });
	}, []);

	// -----------------------------------------------------------------------
	// Completion
	// -----------------------------------------------------------------------

	const queryClient = useQueryClient();

	const completeOnboarding = useCallback(async () => {
		const pid = personaIdRef.current;
		if (!pid || !isValidUUID(pid)) {
			throw new Error("Cannot complete onboarding without a valid persona");
		}

		dispatch({ type: "SET_COMPLETING", completing: true });
		try {
			await apiPatch(`/personas/${pid}`, { onboarding_complete: true });
			void apiPost(`/personas/${pid}/refresh`).catch(() => {});
			await queryClient.invalidateQueries({ queryKey: queryKeys.personas });
		} finally {
			dispatch({ type: "SET_COMPLETING", completing: false });
		}
	}, [queryClient]);

	// -----------------------------------------------------------------------
	// Derived values
	// -----------------------------------------------------------------------

	const stepDef = getStepByNumber(state.currentStep);

	const contextValue = useMemo(
		() => ({
			currentStep: state.currentStep,
			totalSteps: TOTAL_STEPS,
			stepName: stepDef?.name ?? "",
			isStepSkippable: stepDef?.skippable ?? false,
			personaId: state.personaId,
			isLoadingCheckpoint: state.isLoadingCheckpoint,
			isSavingCheckpoint: state.isSavingCheckpoint,
			isCompleting: state.isCompleting,
			resumePrompt: state.resumePrompt,
			completeOnboarding,
			next,
			back,
			skip,
			goToStep,
			restart,
			dismissResumePrompt,
			setPersonaId,
		}),
		[
			state.currentStep,
			state.personaId,
			state.isLoadingCheckpoint,
			state.isSavingCheckpoint,
			state.isCompleting,
			state.resumePrompt,
			stepDef,
			completeOnboarding,
			next,
			back,
			skip,
			goToStep,
			restart,
			dismissResumePrompt,
			setPersonaId,
		],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return <OnboardingContext value={contextValue}>{children}</OnboardingContext>;
}
