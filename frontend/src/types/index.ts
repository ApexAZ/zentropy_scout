/**
 * @fileoverview Barrel re-export of all public domain types.
 *
 * Layer: type-definitions
 * Feature: shared
 *
 * Aggregates type exports from the 11 domain type modules so consumers
 * can import from `@/types` instead of `@/types/<module>`. In practice,
 * most consumers import directly from the specific module files.
 *
 * Coordinates with:
 * - types/api.ts: response envelope types
 * - types/persona.ts: persona + sub-entity types
 * - types/job.ts: job posting + scoring types
 * - types/resume.ts, types/application.ts: document domain types
 * - types/chat.ts, types/sse.ts: real-time communication types
 * - types/ingest.ts, types/source.ts: job ingest and source preferences
 * - types/usage.ts, types/admin.ts: billing and admin resource types
 *
 * Called by / Used by:
 * - (barrel file — most consumers import from specific type modules directly)
 */

export type {
	ApiListResponse,
	ApiResponse,
	ErrorDetail,
	ErrorResponse,
	PaginationMeta,
} from "./api";

export type {
	ChatHandlers,
	ChatMessage,
	ChatMessageRole,
	ToolExecution,
	ToolExecutionStatus,
} from "./chat";

export type {
	ChatDoneEvent,
	ChatTokenEvent,
	DataChangedEvent,
	HeartbeatEvent,
	SSEEvent,
	ToolResultEvent,
	ToolStartEvent,
} from "./sse";

export { isSSEEvent, parseSSEEvent } from "./sse";

export type {
	AchievementStory,
	Bullet,
	Certification,
	ChangeFlagResolution,
	ChangeFlagStatus,
	ChangeType,
	CompanySizePreference,
	CustomNonNegotiable,
	Education,
	FilterType,
	MaxTravelPercent,
	Persona,
	PersonaChangeFlag,
	PollingFrequency,
	Proficiency,
	RemotePreference,
	Skill,
	SkillType,
	StretchAppetite,
	VoiceProfile,
	WorkHistory,
	WorkModel,
} from "./persona";

export {
	CHANGE_FLAG_RESOLUTIONS,
	CHANGE_FLAG_STATUSES,
	CHANGE_TYPES,
	COMPANY_SIZE_PREFERENCES,
	FILTER_TYPES,
	MAX_TRAVEL_PERCENTS,
	POLLING_FREQUENCIES,
	PROFICIENCIES,
	REMOTE_PREFERENCES,
	STRETCH_APPETITES,
	WORK_MODELS,
} from "./persona";

export type {
	DiscoveryMethod,
	ExtractedSkill,
	FailedNonNegotiable,
	FitScoreComponentKey,
	FitScoreResult,
	FitScoreTier,
	GhostScoreTier,
	GhostSignals,
	JobPostingResponse,
	JobPostingStatus,
	PersonaJobResponse,
	ScoreDetails,
	ScoreExplanation,
	SeniorityLevel,
	StretchScoreComponentKey,
	StretchScoreResult,
	StretchScoreTier,
} from "./job";

export {
	FIT_SCORE_COMPONENT_KEYS,
	FIT_SCORE_TIERS,
	GHOST_SCORE_TIERS,
	JOB_POSTING_STATUSES,
	SENIORITY_LEVELS,
	STRETCH_SCORE_COMPONENT_KEYS,
	STRETCH_SCORE_TIERS,
} from "./job";

export type {
	BaseResume,
	BaseResumeStatus,
	GuardrailResult,
	GuardrailSeverity,
	GuardrailViolation,
	JobVariant,
	JobVariantStatus,
	ResumeFile,
	ResumeFileType,
	ResumeSourceType,
	SubmittedResumePDF,
} from "./resume";

export {
	BASE_RESUME_STATUSES,
	GUARDRAIL_SEVERITIES,
	JOB_VARIANT_STATUSES,
	RESUME_FILE_TYPES,
	RESUME_SOURCE_TYPES,
} from "./resume";

export type {
	Application,
	ApplicationStatus,
	CoverLetter,
	CoverLetterStatus,
	CoverLetterValidation,
	InterviewStage,
	JobSnapshot,
	OfferDetails,
	RejectionDetails,
	SubmittedCoverLetterPDF,
	TimelineEvent,
	TimelineEventType,
	ValidationIssue,
	ValidationSeverity,
} from "./application";

export {
	APPLICATION_STATUSES,
	COVER_LETTER_STATUSES,
	INTERVIEW_STAGES,
	TIMELINE_EVENT_TYPES,
	VALIDATION_SEVERITIES,
} from "./application";

export type {
	ExtractedSkillPreview,
	IngestConfirmRequest,
	IngestJobPostingRequest,
	IngestJobPostingResponse,
	IngestPreview,
	IngestSourceName,
} from "./ingest";

export { INGEST_SOURCE_NAMES } from "./ingest";

export type { JobSource, SourceType, UserSourcePreference } from "./source";

export { SOURCE_TYPES } from "./source";

export type {
	BalanceResponse,
	CreditTransactionResponse,
	ProviderSummary,
	TaskTypeSummary,
	UsageRecordResponse,
	UsageSummaryResponse,
} from "./usage";

export type {
	AdminUserItem,
	AdminUserUpdateRequest,
	CacheRefreshResult,
	FundingPackCreateRequest,
	FundingPackItem,
	FundingPackUpdateRequest,
	ModelRegistryCreateRequest,
	ModelRegistryItem,
	ModelRegistryUpdateRequest,
	PricingConfigCreateRequest,
	PricingConfigItem,
	PricingConfigUpdateRequest,
	SystemConfigItem,
	SystemConfigUpsertRequest,
	TaskRoutingCreateRequest,
	TaskRoutingItem,
	TaskRoutingUpdateRequest,
} from "./admin";
