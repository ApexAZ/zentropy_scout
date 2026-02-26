"use client";

/**
 * Onboarding page.
 *
 * REQ-019 §7.1: 11-step onboarding wizard.
 * Wraps all step components in OnboardingProvider and OnboardingShell,
 * routing to the correct step based on provider state.
 */

import { Loader2 } from "lucide-react";

import { OnboardingShell } from "@/components/onboarding/onboarding-shell";
import { BasicInfoStep } from "@/components/onboarding/steps/basic-info-step";
import { CertificationStep } from "@/components/onboarding/steps/certification-step";
import { EducationStep } from "@/components/onboarding/steps/education-step";
import { GrowthTargetsStep } from "@/components/onboarding/steps/growth-targets-step";
import { NonNegotiablesStep } from "@/components/onboarding/steps/non-negotiables-step";
import { ResumeUploadStep } from "@/components/onboarding/steps/resume-upload-step";
import { ReviewStep } from "@/components/onboarding/steps/review-step";
import { SkillsStep } from "@/components/onboarding/steps/skills-step";
import { StoryStep } from "@/components/onboarding/steps/story-step";
import { VoiceProfileStep } from "@/components/onboarding/steps/voice-profile-step";
import { WorkHistoryStep } from "@/components/onboarding/steps/work-history-step";
import { OnboardingProvider, useOnboarding } from "@/lib/onboarding-provider";

function StepRouter() {
	const { currentStep } = useOnboarding();

	switch (currentStep) {
		case 1:
			return <ResumeUploadStep />;
		case 2:
			return <BasicInfoStep />;
		case 3:
			return <WorkHistoryStep />;
		case 4:
			return <EducationStep />;
		case 5:
			return <SkillsStep />;
		case 6:
			return <CertificationStep />;
		case 7:
			return <StoryStep />;
		case 8:
			return <NonNegotiablesStep />;
		case 9:
			return <GrowthTargetsStep />;
		case 10:
			return <VoiceProfileStep />;
		case 11:
			return <ReviewStep />;
		default:
			return null;
	}
}

function OnboardingContent() {
	const {
		currentStep,
		totalSteps,
		stepName,
		isStepSkippable,
		isLoadingCheckpoint,
		next,
		back,
		skip,
	} = useOnboarding();

	if (isLoadingCheckpoint) {
		return (
			<main className="flex min-h-screen items-center justify-center">
				<Loader2
					className="text-primary h-8 w-8 animate-spin"
					data-testid="onboarding-loading"
				/>
			</main>
		);
	}

	return (
		<OnboardingShell
			currentStep={currentStep}
			totalSteps={totalSteps}
			stepName={stepName}
			onNext={next}
			onBack={currentStep > 1 ? back : undefined}
			onSkip={isStepSkippable ? skip : undefined}
		>
			<StepRouter />
		</OnboardingShell>
	);
}

export default function OnboardingPage() {
	return (
		<OnboardingProvider>
			<OnboardingContent />
		</OnboardingProvider>
	);
}
