/**
 * Tests for message bubble components.
 *
 * REQ-012 §5.2: Message types with role-based alignment and styling.
 * User messages right-aligned with primary color, agent messages
 * left-aligned with muted background, system notices centered.
 */

import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";

import type {
	ChatCard,
	ChatMessage,
	ConfirmCardData,
	JobCardData,
	OptionListData,
	ScoreCardData,
} from "@/types/chat";

import { MessageBubble } from "./message-bubble";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const USER_MESSAGE: ChatMessage = {
	id: "msg-user-1",
	role: "user",
	content: "Hello, can you help me find a job?",
	timestamp: "2026-02-11T10:30:00.000Z",
	isStreaming: false,
	tools: [],
	cards: [],
};

const AGENT_MESSAGE: ChatMessage = {
	id: "msg-agent-1",
	role: "agent",
	content: "Of course! Let me search for matching positions.",
	timestamp: "2026-02-11T10:30:05.000Z",
	isStreaming: false,
	tools: [],
	cards: [],
};

const SYSTEM_MESSAGE: ChatMessage = {
	id: "msg-system-1",
	role: "system",
	content: "Connected to Scout",
	timestamp: "2026-02-11T10:29:55.000Z",
	isStreaming: false,
	tools: [],
	cards: [],
};

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

const BUBBLE_SELECTOR = '[data-slot="message-bubble"]';
const CONTENT_SELECTOR = '[data-slot="message-content"]';
const TIMESTAMP_SELECTOR = '[data-slot="message-timestamp"]';
const NOTICE_SELECTOR = '[data-slot="system-notice"]';
const CURSOR_SELECTOR = '[data-slot="streaming-cursor"]';
const TOOL_BADGE_SELECTOR = '[data-slot="tool-execution"]';
const TOOLS_CONTAINER_SELECTOR = '[data-slot="tool-executions"]';
const CARDS_CONTAINER_SELECTOR = '[data-slot="chat-cards"]';
const JOB_CARD_SELECTOR = '[data-slot="chat-job-card"]';
const SCORE_CARD_SELECTOR = '[data-slot="chat-score-card"]';
const OPTION_LIST_SELECTOR = '[data-slot="chat-option-list"]';
const CONFIRM_CARD_SELECTOR = '[data-slot="chat-confirm-card"]';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderBubble(
	props: Partial<ComponentProps<typeof MessageBubble>> = {},
) {
	return render(<MessageBubble message={USER_MESSAGE} {...props} />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("MessageBubble", () => {
	// -----------------------------------------------------------------------
	// User messages
	// -----------------------------------------------------------------------

	describe("user message", () => {
		it("renders message content", () => {
			renderBubble();

			expect(screen.getByText(USER_MESSAGE.content)).toBeInTheDocument();
		});

		it("has right alignment", () => {
			const { container } = renderBubble();

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveClass("justify-end");
		});

		it("uses primary color background", () => {
			const { container } = renderBubble();

			const content = container.querySelector(CONTENT_SELECTOR);
			expect(content).toHaveClass("bg-primary");
			expect(content).toHaveClass("text-primary-foreground");
		});

		it("displays timestamp", () => {
			const { container } = renderBubble();

			const timestamp = container.querySelector(TIMESTAMP_SELECTOR);
			expect(timestamp).toBeInTheDocument();
			expect(timestamp?.textContent).toBeTruthy();
		});

		it("has data-role attribute", () => {
			const { container } = renderBubble();

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveAttribute("data-role", "user");
		});

		it("merges custom className on wrapper", () => {
			const { container } = renderBubble({ className: "my-custom" });

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveClass("my-custom");
		});
	});

	// -----------------------------------------------------------------------
	// Agent messages
	// -----------------------------------------------------------------------

	describe("agent message", () => {
		it("renders message content", () => {
			renderBubble({ message: AGENT_MESSAGE });

			expect(screen.getByText(AGENT_MESSAGE.content)).toBeInTheDocument();
		});

		it("has left alignment", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveClass("justify-start");
		});

		it("uses muted background", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			const content = container.querySelector(CONTENT_SELECTOR);
			expect(content).toHaveClass("bg-muted");
			expect(content).toHaveClass("text-foreground");
		});

		it("displays timestamp", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			const timestamp = container.querySelector(TIMESTAMP_SELECTOR);
			expect(timestamp).toBeInTheDocument();
			expect(timestamp?.textContent).toBeTruthy();
		});

		it("has data-role attribute", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveAttribute("data-role", "agent");
		});
	});

	// -----------------------------------------------------------------------
	// System notices
	// -----------------------------------------------------------------------

	describe("system notice", () => {
		it("renders notice content", () => {
			renderBubble({ message: SYSTEM_MESSAGE });

			expect(screen.getByText(SYSTEM_MESSAGE.content)).toBeInTheDocument();
		});

		it("has center alignment", () => {
			const { container } = renderBubble({ message: SYSTEM_MESSAGE });

			const notice = container.querySelector(NOTICE_SELECTOR);
			expect(notice).toHaveClass("text-center");
		});

		it("uses muted small text styling", () => {
			const { container } = renderBubble({ message: SYSTEM_MESSAGE });

			const notice = container.querySelector(NOTICE_SELECTOR);
			expect(notice).toHaveClass("text-muted-foreground");
			expect(notice).toHaveClass("text-xs");
		});

		it("has data-role attribute", () => {
			const { container } = renderBubble({ message: SYSTEM_MESSAGE });

			const notice = container.querySelector(NOTICE_SELECTOR);
			expect(notice).toHaveAttribute("data-role", "system");
		});

		it("does not render a bubble content wrapper", () => {
			const { container } = renderBubble({ message: SYSTEM_MESSAGE });

			expect(container.querySelector(CONTENT_SELECTOR)).not.toBeInTheDocument();
		});

		it("does not render a timestamp", () => {
			const { container } = renderBubble({ message: SYSTEM_MESSAGE });

			expect(
				container.querySelector(TIMESTAMP_SELECTOR),
			).not.toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Accessibility
	// -----------------------------------------------------------------------

	describe("accessibility", () => {
		it("system notice has status role", () => {
			renderBubble({ message: SYSTEM_MESSAGE });

			expect(screen.getByRole("status")).toBeInTheDocument();
		});

		it("user message timestamp uses time element with dateTime", () => {
			const { container } = renderBubble();

			const time = container.querySelector("time");
			expect(time).toBeInTheDocument();
			expect(time).toHaveAttribute("dateTime", USER_MESSAGE.timestamp);
		});

		it("agent message timestamp uses time element with dateTime", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			const time = container.querySelector("time");
			expect(time).toBeInTheDocument();
			expect(time).toHaveAttribute("dateTime", AGENT_MESSAGE.timestamp);
		});

		it("user message has aria-label identifying sender", () => {
			const { container } = renderBubble();

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveAttribute(
				"aria-label",
				expect.stringContaining("You"),
			);
		});

		it("agent message has aria-label identifying sender", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveAttribute(
				"aria-label",
				expect.stringContaining("Scout"),
			);
		});
	});

	// -----------------------------------------------------------------------
	// Security
	// -----------------------------------------------------------------------

	describe("security", () => {
		it("renders HTML-like content as plain text, not as HTML elements", () => {
			const xssContent = '<script>alert("xss")</script>';
			const xssMsg: ChatMessage = {
				...USER_MESSAGE,
				content: xssContent,
			};
			renderBubble({ message: xssMsg });

			expect(screen.getByText(xssContent)).toBeInTheDocument();
		});

		it("renders HTML attributes in content as plain text", () => {
			const imgContent = "<img src=x onerror=alert(1)>";
			const imgMsg: ChatMessage = {
				...AGENT_MESSAGE,
				content: imgContent,
			};
			renderBubble({ message: imgMsg });

			expect(screen.getByText(imgContent)).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Edge cases
	// -----------------------------------------------------------------------

	describe("edge cases", () => {
		it("renders empty content gracefully", () => {
			const emptyMsg: ChatMessage = { ...USER_MESSAGE, content: "" };
			const { container } = renderBubble({ message: emptyMsg });

			expect(container.querySelector(BUBBLE_SELECTOR)).toBeInTheDocument();
		});

		it("renders fallback text for invalid ISO timestamp", () => {
			const badTimestamp: ChatMessage = {
				...USER_MESSAGE,
				timestamp: "not-a-date",
			};
			const { container } = renderBubble({ message: badTimestamp });

			const timestamp = container.querySelector(TIMESTAMP_SELECTOR);
			expect(timestamp).toBeInTheDocument();
			// Should not contain "Invalid Date" or be empty — should display a fallback
			expect(timestamp?.textContent).toBeTruthy();
			expect(timestamp?.textContent).not.toContain("Invalid Date");
		});

		it("renders long content without breaking layout", () => {
			const longMsg: ChatMessage = {
				...AGENT_MESSAGE,
				content: "x".repeat(5000),
			};
			const { container } = renderBubble({ message: longMsg });

			const content = container.querySelector(CONTENT_SELECTOR);
			expect(content).toBeInTheDocument();
			expect(content).toHaveClass("break-words");
		});

		it("renders streaming agent message", () => {
			const streamingMsg: ChatMessage = {
				...AGENT_MESSAGE,
				isStreaming: true,
			};
			const { container } = renderBubble({ message: streamingMsg });

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveAttribute("data-streaming", "true");
		});

		it("non-streaming message has data-streaming false", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			const wrapper = container.querySelector(BUBBLE_SELECTOR);
			expect(wrapper).toHaveAttribute("data-streaming", "false");
		});
	});

	// -----------------------------------------------------------------------
	// Tool execution badges (REQ-012 §5.4)
	// -----------------------------------------------------------------------

	describe("tool execution badges", () => {
		it("renders tool badges for agent messages with tools", () => {
			const msg: ChatMessage = {
				...AGENT_MESSAGE,
				tools: [{ tool: "favorite_job", args: {}, status: "success" }],
			};
			const { container } = renderBubble({ message: msg });

			expect(container.querySelector(TOOL_BADGE_SELECTOR)).toBeInTheDocument();
		});

		it("renders multiple tool badges", () => {
			const msg: ChatMessage = {
				...AGENT_MESSAGE,
				tools: [
					{ tool: "search_jobs", args: {}, status: "success" },
					{ tool: "score_posting", args: {}, status: "running" },
				],
			};
			const { container } = renderBubble({ message: msg });

			const badges = container.querySelectorAll(TOOL_BADGE_SELECTOR);
			expect(badges).toHaveLength(2);
		});

		it("does not render tools container when tools array is empty", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			expect(
				container.querySelector(TOOLS_CONTAINER_SELECTOR),
			).not.toBeInTheDocument();
		});

		it("does not render tool badges for user messages", () => {
			const msg: ChatMessage = {
				...USER_MESSAGE,
				tools: [{ tool: "favorite_job", args: {}, status: "success" }],
			};
			const { container } = renderBubble({ message: msg });

			expect(
				container.querySelector(TOOL_BADGE_SELECTOR),
			).not.toBeInTheDocument();
		});

		it("does not render tool badges for system messages", () => {
			const msg: ChatMessage = {
				...SYSTEM_MESSAGE,
				tools: [{ tool: "favorite_job", args: {}, status: "success" }],
			};
			const { container } = renderBubble({ message: msg });

			expect(
				container.querySelector(TOOL_BADGE_SELECTOR),
			).not.toBeInTheDocument();
		});

		it("tools container has aria-live for screen readers", () => {
			const msg: ChatMessage = {
				...AGENT_MESSAGE,
				tools: [{ tool: "favorite_job", args: {}, status: "running" }],
			};
			const { container } = renderBubble({ message: msg });

			const toolsContainer = container.querySelector(TOOLS_CONTAINER_SELECTOR);
			expect(toolsContainer).toHaveAttribute("aria-live", "polite");
		});

		it("tool badges appear between content and timestamp", () => {
			const msg: ChatMessage = {
				...AGENT_MESSAGE,
				tools: [{ tool: "favorite_job", args: {}, status: "success" }],
			};
			const { container } = renderBubble({ message: msg });

			const content = container.querySelector(CONTENT_SELECTOR);
			const toolsContainer = container.querySelector(TOOLS_CONTAINER_SELECTOR);
			const timestamp = container.querySelector(TIMESTAMP_SELECTOR);

			expect(content).toBeInTheDocument();
			expect(toolsContainer).toBeInTheDocument();
			expect(timestamp).toBeInTheDocument();

			// Verify DOM order: content → tools → timestamp
			const parent = content?.parentElement;
			const children = Array.from(parent?.children ?? []);
			const contentIdx = children.indexOf(content as Element);
			const toolsIdx = children.indexOf(toolsContainer as Element);
			const timestampIdx = children.indexOf(timestamp as Element);
			expect(contentIdx).toBeLessThan(toolsIdx);
			expect(toolsIdx).toBeLessThan(timestampIdx);
		});
	});

	// -----------------------------------------------------------------------
	// Streaming cursor (REQ-012 §5.4)
	// -----------------------------------------------------------------------

	describe("streaming cursor", () => {
		it("shows cursor when agent message is streaming", () => {
			const streamingMsg: ChatMessage = {
				...AGENT_MESSAGE,
				isStreaming: true,
			};
			const { container } = renderBubble({ message: streamingMsg });

			expect(container.querySelector(CURSOR_SELECTOR)).toBeInTheDocument();
		});

		it("does not show cursor when agent message is not streaming", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			expect(container.querySelector(CURSOR_SELECTOR)).not.toBeInTheDocument();
		});

		it("does not show cursor for user messages", () => {
			const streamingUser: ChatMessage = {
				...USER_MESSAGE,
				isStreaming: true,
			};
			const { container } = renderBubble({ message: streamingUser });

			expect(container.querySelector(CURSOR_SELECTOR)).not.toBeInTheDocument();
		});

		it("does not show cursor for system notices", () => {
			const streamingSystem: ChatMessage = {
				...SYSTEM_MESSAGE,
				isStreaming: true,
			};
			const { container } = renderBubble({ message: streamingSystem });

			expect(container.querySelector(CURSOR_SELECTOR)).not.toBeInTheDocument();
		});

		it("cursor is inside the content bubble", () => {
			const streamingMsg: ChatMessage = {
				...AGENT_MESSAGE,
				isStreaming: true,
			};
			const { container } = renderBubble({ message: streamingMsg });

			const content = container.querySelector(CONTENT_SELECTOR);
			const cursor = content?.querySelector(CURSOR_SELECTOR);
			expect(cursor).toBeInTheDocument();
		});
	});

	// -----------------------------------------------------------------------
	// Structured chat cards (REQ-012 §5.3)
	// -----------------------------------------------------------------------

	describe("structured chat cards", () => {
		const JOB_CARD_DATA: JobCardData = {
			jobId: "job-123",
			jobTitle: "Senior Dev",
			companyName: "Acme",
			location: "NYC",
			workModel: "Remote",
			fitScore: 90,
			stretchScore: 50,
			salaryMin: 100_000,
			salaryMax: 150_000,
			salaryCurrency: "USD",
			isFavorite: false,
		};

		const SCORE_CARD_DATA: ScoreCardData = {
			jobId: "job-123",
			jobTitle: "Senior Dev",
			fit: {
				total: 90,
				components: {
					hard_skills: 85,
					soft_skills: 90,
					experience_level: 95,
					role_title: 88,
					location_logistics: 100,
				},
				weights: {
					hard_skills: 0.4,
					soft_skills: 0.15,
					experience_level: 0.25,
					role_title: 0.1,
					location_logistics: 0.1,
				},
			},
			stretch: {
				total: 50,
				components: {
					target_role: 55,
					target_skills: 45,
					growth_trajectory: 50,
				},
				weights: {
					target_role: 0.5,
					target_skills: 0.4,
					growth_trajectory: 0.1,
				},
			},
			explanation: {
				summary: "Good match.",
				strengths: ["Python"],
				gaps: ["K8s"],
				stretch_opportunities: [],
				warnings: [],
			},
		};

		const JOB_CARD: ChatCard = { type: "job", data: JOB_CARD_DATA };
		const SCORE_CARD: ChatCard = { type: "score", data: SCORE_CARD_DATA };

		it("renders job card for agent message with cards", () => {
			const msg: ChatMessage = {
				...AGENT_MESSAGE,
				cards: [JOB_CARD],
			};
			const { container } = renderBubble({ message: msg });

			expect(container.querySelector(JOB_CARD_SELECTOR)).toBeInTheDocument();
		});

		it("renders score card for agent message with cards", () => {
			const msg: ChatMessage = {
				...AGENT_MESSAGE,
				cards: [SCORE_CARD],
			};
			const { container } = renderBubble({ message: msg });

			expect(container.querySelector(SCORE_CARD_SELECTOR)).toBeInTheDocument();
		});

		it("renders multiple cards", () => {
			const msg: ChatMessage = {
				...AGENT_MESSAGE,
				cards: [JOB_CARD, SCORE_CARD],
			};
			const { container } = renderBubble({ message: msg });

			expect(container.querySelector(JOB_CARD_SELECTOR)).toBeInTheDocument();
			expect(container.querySelector(SCORE_CARD_SELECTOR)).toBeInTheDocument();
		});

		it("does not render cards container when cards array is empty", () => {
			const { container } = renderBubble({ message: AGENT_MESSAGE });

			expect(
				container.querySelector(CARDS_CONTAINER_SELECTOR),
			).not.toBeInTheDocument();
		});

		it("does not render cards for user messages", () => {
			const msg: ChatMessage = {
				...USER_MESSAGE,
				cards: [JOB_CARD],
			};
			const { container } = renderBubble({ message: msg });

			expect(
				container.querySelector(JOB_CARD_SELECTOR),
			).not.toBeInTheDocument();
		});

		it("does not render cards for system messages", () => {
			const msg: ChatMessage = {
				...SYSTEM_MESSAGE,
				cards: [JOB_CARD],
			};
			const { container } = renderBubble({ message: msg });

			expect(
				container.querySelector(JOB_CARD_SELECTOR),
			).not.toBeInTheDocument();
		});

		it("cards appear between content and tool badges", () => {
			const msg: ChatMessage = {
				...AGENT_MESSAGE,
				cards: [JOB_CARD],
				tools: [{ tool: "search_jobs", args: {}, status: "success" }],
			};
			const { container } = renderBubble({ message: msg });

			const content = container.querySelector(CONTENT_SELECTOR);
			const cardsContainer = container.querySelector(CARDS_CONTAINER_SELECTOR);
			const toolsContainer = container.querySelector(TOOLS_CONTAINER_SELECTOR);

			expect(content).toBeInTheDocument();
			expect(cardsContainer).toBeInTheDocument();
			expect(toolsContainer).toBeInTheDocument();

			// Verify DOM order: content → cards → tools
			const parent = content?.parentElement;
			const children = Array.from(parent?.children ?? []);
			const contentIdx = children.indexOf(content as Element);
			const cardsIdx = children.indexOf(cardsContainer as Element);
			const toolsIdx = children.indexOf(toolsContainer as Element);
			expect(contentIdx).toBeLessThan(cardsIdx);
			expect(cardsIdx).toBeLessThan(toolsIdx);
		});
	});

	// -----------------------------------------------------------------------
	// Ambiguity resolution cards (REQ-012 §5.6)
	// -----------------------------------------------------------------------

	describe("ambiguity resolution cards", () => {
		const OPTION_LIST_DATA: OptionListData = {
			options: [
				{ label: "Scrum Master at Acme Corp", value: "1" },
				{ label: "Product Owner at TechCo", value: "2" },
			],
		};

		const CONFIRM_DATA: ConfirmCardData = {
			message: "Are you sure you want to dismiss this job?",
			isDestructive: true,
		};

		const OPTION_CARD: ChatCard = {
			type: "options",
			data: OPTION_LIST_DATA,
		};
		const CONFIRM_CARD: ChatCard = {
			type: "confirm",
			data: CONFIRM_DATA,
		};

		it("renders option list card for agent message", () => {
			const msg: ChatMessage = {
				...AGENT_MESSAGE,
				cards: [OPTION_CARD],
			};
			const { container } = renderBubble({ message: msg });

			expect(container.querySelector(OPTION_LIST_SELECTOR)).toBeInTheDocument();
		});

		it("renders confirm card for agent message", () => {
			const msg: ChatMessage = {
				...AGENT_MESSAGE,
				cards: [CONFIRM_CARD],
			};
			const { container } = renderBubble({ message: msg });

			expect(
				container.querySelector(CONFIRM_CARD_SELECTOR),
			).toBeInTheDocument();
		});

		it("does not render option list for user messages", () => {
			const msg: ChatMessage = {
				...USER_MESSAGE,
				cards: [OPTION_CARD],
			};
			const { container } = renderBubble({ message: msg });

			expect(
				container.querySelector(OPTION_LIST_SELECTOR),
			).not.toBeInTheDocument();
		});

		it("does not render confirm card for user messages", () => {
			const msg: ChatMessage = {
				...USER_MESSAGE,
				cards: [CONFIRM_CARD],
			};
			const { container } = renderBubble({ message: msg });

			expect(
				container.querySelector(CONFIRM_CARD_SELECTOR),
			).not.toBeInTheDocument();
		});

		it("renders mixed card types together", () => {
			const msg: ChatMessage = {
				...AGENT_MESSAGE,
				cards: [OPTION_CARD, CONFIRM_CARD],
			};
			const { container } = renderBubble({ message: msg });

			expect(container.querySelector(OPTION_LIST_SELECTOR)).toBeInTheDocument();
			expect(
				container.querySelector(CONFIRM_CARD_SELECTOR),
			).toBeInTheDocument();
		});
	});
});
