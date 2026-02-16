/**
 * Mock data factories for chat E2E tests.
 *
 * Returns chat messages, tool executions, and structured cards matching
 * the ChatMessage, ToolExecution, and ChatCard types from chat.ts.
 */

import type { ApiListResponse } from "@/types/api";
import type { Persona } from "@/types/persona";
import type {
	ChatCard,
	ChatMessage,
	ToolExecution,
	ToolExecutionStatus,
} from "@/types/chat";

import { personaList } from "./onboarding-mock-data";

// ---------------------------------------------------------------------------
// Re-exports
// ---------------------------------------------------------------------------

export { PERSONA_ID } from "./onboarding-mock-data";

// ---------------------------------------------------------------------------
// Consistent IDs
// ---------------------------------------------------------------------------

export const CHAT_MSG_IDS = [
	"chat-msg-001",
	"chat-msg-002",
	"chat-msg-003",
	"chat-msg-004",
	"chat-msg-005",
	"chat-msg-006",
] as const;

export const JOB_ID = "job-chat-001";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NOW = "2026-02-15T12:00:00Z";

// ---------------------------------------------------------------------------
// Message factories
// ---------------------------------------------------------------------------

/** User message factory. */
export function userMessage(overrides?: Partial<ChatMessage>): ChatMessage {
	return {
		id: CHAT_MSG_IDS[0],
		role: "user",
		content: "Find me React developer jobs in Austin",
		timestamp: NOW,
		isStreaming: false,
		tools: [],
		cards: [],
		...overrides,
	};
}

/** Agent message factory. */
export function agentMessage(overrides?: Partial<ChatMessage>): ChatMessage {
	return {
		id: CHAT_MSG_IDS[1],
		role: "agent",
		content:
			"I found several React developer positions in Austin. Let me show you the top matches.",
		timestamp: NOW,
		isStreaming: false,
		tools: [],
		cards: [],
		...overrides,
	};
}

/** Agent message with a tool execution badge. */
export function agentMessageWithTool(
	tool: string,
	status: ToolExecutionStatus,
): ChatMessage {
	const execution: ToolExecution = {
		tool,
		args: { query: "React developer Austin" },
		status,
	};
	return agentMessage({
		id: CHAT_MSG_IDS[2],
		content: "Searching for matching positions...",
		tools: [execution],
	});
}

/** Agent message with a job card. */
export function agentMessageWithJobCard(): ChatMessage {
	const jobCard: ChatCard = {
		type: "job",
		data: {
			jobId: JOB_ID,
			jobTitle: "Senior React Developer",
			companyName: "TechCorp",
			location: "Austin, TX",
			workModel: "Hybrid",
			fitScore: 85,
			stretchScore: 42,
			salaryMin: 140000,
			salaryMax: 160000,
			salaryCurrency: "USD",
			isFavorite: false,
		},
	};
	return agentMessage({
		id: CHAT_MSG_IDS[3],
		content: "Here is a great match for you:",
		cards: [jobCard],
	});
}

/** Agent message with a score card. */
export function agentMessageWithScoreCard(): ChatMessage {
	const scoreCard: ChatCard = {
		type: "score",
		data: {
			jobId: JOB_ID,
			jobTitle: "Senior React Developer",
			fit: {
				total: 85,
				components: {
					hard_skills: 90,
					soft_skills: 80,
					experience_level: 85,
					role_title: 88,
					location_logistics: 82,
				},
				weights: {
					hard_skills: 0.3,
					soft_skills: 0.15,
					experience_level: 0.25,
					role_title: 0.15,
					location_logistics: 0.15,
				},
			},
			stretch: {
				total: 42,
				components: {
					target_role: 50,
					target_skills: 40,
					growth_trajectory: 35,
				},
				weights: {
					target_role: 0.4,
					target_skills: 0.35,
					growth_trajectory: 0.25,
				},
			},
			explanation: {
				summary: "Strong fit for this role with good technical alignment.",
				strengths: ["React expertise", "TypeScript proficiency"],
				gaps: ["AWS experience"],
				stretch_opportunities: ["Team leadership"],
				warnings: [],
			},
		},
	};
	return agentMessage({
		id: CHAT_MSG_IDS[4],
		content: "Here is the detailed score breakdown:",
		cards: [scoreCard],
	});
}

/** Agent message with an option list. */
export function agentMessageWithOptions(): ChatMessage {
	const optionCard: ChatCard = {
		type: "options",
		data: {
			options: [
				{ label: "Senior React Developer at TechCorp", value: "1" },
				{ label: "Lead Frontend Engineer at StartupX", value: "2" },
				{ label: "Full Stack Developer at BigCo", value: "3" },
			],
		},
	};
	return agentMessage({
		id: CHAT_MSG_IDS[5],
		content: "Which position would you like to learn more about?",
		cards: [optionCard],
	});
}

// ---------------------------------------------------------------------------
// Chat history response factories
// ---------------------------------------------------------------------------

/** Chat history with 4 basic messages (user, agent, user, agent). */
export function chatHistoryResponse(): ChatMessage[] {
	return [
		userMessage({ id: CHAT_MSG_IDS[0], content: "What jobs are available?" }),
		agentMessage({
			id: CHAT_MSG_IDS[1],
			content: "I can help you find jobs. What role are you looking for?",
		}),
		userMessage({
			id: CHAT_MSG_IDS[2],
			content: "React developer in Austin",
		}),
		agentMessage({
			id: CHAT_MSG_IDS[3],
			content: "I found several React positions in Austin.",
		}),
	];
}

/** Chat history including job card and score card messages. */
export function chatHistoryWithCards(): ChatMessage[] {
	return [
		userMessage({ id: CHAT_MSG_IDS[0], content: "Show me matching jobs" }),
		agentMessageWithJobCard(),
		userMessage({
			id: CHAT_MSG_IDS[4],
			content: "Tell me more about this one",
		}),
		agentMessageWithScoreCard(),
	];
}

/** Chat history including option list message. */
export function chatHistoryWithOptions(): ChatMessage[] {
	return [
		userMessage({ id: CHAT_MSG_IDS[0], content: "I need help choosing" }),
		agentMessageWithOptions(),
	];
}

// ---------------------------------------------------------------------------
// Persona factory (onboarded wrapper)
// ---------------------------------------------------------------------------

/** Onboarded persona list for chat tests. */
export function onboardedPersonaList(): ApiListResponse<Persona> {
	return personaList({ onboarding_complete: true, onboarding_step: null });
}
