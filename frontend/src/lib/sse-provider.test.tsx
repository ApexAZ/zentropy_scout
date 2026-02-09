/**
 * Tests for the SSE React context provider.
 *
 * REQ-012 §4.4: SSEProvider wraps the SSEClient in a React context,
 * wires the SSE-to-TanStack-Query bridge, and exposes connection
 * status to the component tree.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SSEClientConfig } from "./sse-client";
import { SSEProvider, useSSE } from "./sse-provider";

// ---------------------------------------------------------------------------
// Test constants
// ---------------------------------------------------------------------------

const DEFAULT_SSE_URL = "/api/v1/chat/stream";
const CUSTOM_SSE_URL = "/custom/stream";
const TEST_RESOURCE = "job-posting";
const TEST_ID = "abc-123";
const TEST_ACTION = "updated";
const STATUS_TEST_ID = "status";
const CHILD_TEST_ID = "child";

// ---------------------------------------------------------------------------
// Mocks (vi.hoisted ensures availability inside vi.mock factories)
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => {
	const mockConnect = vi.fn();
	const mockDestroy = vi.fn();
	const mockOnDataChanged = vi.fn();
	const mockOnReconnect = vi.fn();
	let capturedConfig: SSEClientConfig | null = null;

	return {
		mockConnect,
		mockDestroy,
		mockOnDataChanged,
		mockOnReconnect,
		getCapturedConfig: () => capturedConfig,
		setCapturedConfig: (config: SSEClientConfig | null) => {
			capturedConfig = config;
		},
	};
});

vi.mock("./sse-client", () => {
	// Use a regular function (not arrow) so it can be called with `new`
	function MockSSEClient(
		this: Record<string, unknown>,
		config: SSEClientConfig,
	) {
		mocks.setCapturedConfig(config);
		this.connect = mocks.mockConnect;
		this.destroy = mocks.mockDestroy;
	}
	return { SSEClient: MockSSEClient };
});

vi.mock("./sse-query-bridge", () => ({
	createSSEQueryBridge: vi.fn(() => ({
		onDataChanged: mocks.mockOnDataChanged,
		onReconnect: mocks.mockOnReconnect,
	})),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createTestQueryClient(): QueryClient {
	return new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
}

function TestWrapper({ children }: { children: ReactNode }) {
	return (
		<QueryClientProvider client={createTestQueryClient()}>
			{children}
		</QueryClientProvider>
	);
}

function StatusDisplay() {
	const { status } = useSSE();
	return <div data-testid={STATUS_TEST_ID}>{status}</div>;
}

// ---------------------------------------------------------------------------
// Shared setup
// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
	mocks.setCapturedConfig(null);
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SSEProvider", () => {
	// -----------------------------------------------------------------------
	// Rendering
	// -----------------------------------------------------------------------

	it("renders children", () => {
		render(
			<SSEProvider>
				<div data-testid={CHILD_TEST_ID}>Hello</div>
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		expect(screen.getByTestId(CHILD_TEST_ID)).toHaveTextContent("Hello");
	});

	// -----------------------------------------------------------------------
	// SSEClient creation
	// -----------------------------------------------------------------------

	it("creates SSEClient with default URL", () => {
		render(
			<SSEProvider>
				<div />
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		const config = mocks.getCapturedConfig();
		expect(config).not.toBeNull();
		expect(config!.url).toBe(DEFAULT_SSE_URL);
	});

	it("creates SSEClient with custom URL", () => {
		render(
			<SSEProvider url={CUSTOM_SSE_URL}>
				<div />
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		expect(mocks.getCapturedConfig()!.url).toBe(CUSTOM_SSE_URL);
	});

	// -----------------------------------------------------------------------
	// Lifecycle
	// -----------------------------------------------------------------------

	it("calls connect() on mount", () => {
		render(
			<SSEProvider>
				<div />
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		expect(mocks.mockConnect).toHaveBeenCalledTimes(1);
	});

	it("calls destroy() on unmount", () => {
		const { unmount } = render(
			<SSEProvider>
				<div />
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		unmount();

		expect(mocks.mockDestroy).toHaveBeenCalledTimes(1);
	});

	it("destroys old client and creates new one when URL changes", () => {
		const queryClient = createTestQueryClient();
		const { rerender } = render(
			<QueryClientProvider client={queryClient}>
				<SSEProvider url="/url-one">
					<div />
				</SSEProvider>
			</QueryClientProvider>,
		);

		expect(mocks.mockConnect).toHaveBeenCalledTimes(1);
		expect(mocks.getCapturedConfig()!.url).toBe("/url-one");

		rerender(
			<QueryClientProvider client={queryClient}>
				<SSEProvider url="/url-two">
					<div />
				</SSEProvider>
			</QueryClientProvider>,
		);

		expect(mocks.mockDestroy).toHaveBeenCalledTimes(1);
		expect(mocks.mockConnect).toHaveBeenCalledTimes(2);
		expect(mocks.getCapturedConfig()!.url).toBe("/url-two");
	});

	// -----------------------------------------------------------------------
	// Bridge wiring
	// -----------------------------------------------------------------------

	it("wires bridge.onDataChanged to SSEClient config", () => {
		render(
			<SSEProvider>
				<div />
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		mocks
			.getCapturedConfig()!
			.onDataChanged(TEST_RESOURCE, TEST_ID, TEST_ACTION);

		expect(mocks.mockOnDataChanged).toHaveBeenCalledWith(
			TEST_RESOURCE,
			TEST_ID,
			TEST_ACTION,
		);
	});

	it("calls bridge.onReconnect when SSEClient reconnects", () => {
		render(
			<SSEProvider>
				<div />
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		act(() => {
			mocks.getCapturedConfig()!.onReconnect();
		});

		expect(mocks.mockOnReconnect).toHaveBeenCalledTimes(1);
	});

	// -----------------------------------------------------------------------
	// Status tracking (via onStatusChange)
	// -----------------------------------------------------------------------

	it("exposes initial status as disconnected", () => {
		render(
			<SSEProvider>
				<StatusDisplay />
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		expect(screen.getByTestId(STATUS_TEST_ID)).toHaveTextContent(
			"disconnected",
		);
	});

	it("wires onStatusChange to SSEClient config", () => {
		render(
			<SSEProvider>
				<StatusDisplay />
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		expect(mocks.getCapturedConfig()!.onStatusChange).toBeDefined();
		expect(typeof mocks.getCapturedConfig()!.onStatusChange).toBe("function");
	});

	it("updates status to connected via onStatusChange", () => {
		render(
			<SSEProvider>
				<StatusDisplay />
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		act(() => {
			mocks.getCapturedConfig()!.onStatusChange!("connected");
		});

		expect(screen.getByTestId(STATUS_TEST_ID)).toHaveTextContent("connected");
	});

	it("updates status to reconnecting via onStatusChange", () => {
		render(
			<SSEProvider>
				<StatusDisplay />
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		act(() => {
			mocks.getCapturedConfig()!.onStatusChange!("reconnecting");
		});

		expect(screen.getByTestId(STATUS_TEST_ID)).toHaveTextContent(
			"reconnecting",
		);
	});

	it("updates status to disconnected via onStatusChange", () => {
		render(
			<SSEProvider>
				<StatusDisplay />
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		// First change to connected, then back to disconnected
		act(() => {
			mocks.getCapturedConfig()!.onStatusChange!("connected");
		});
		expect(screen.getByTestId(STATUS_TEST_ID)).toHaveTextContent("connected");

		act(() => {
			mocks.getCapturedConfig()!.onStatusChange!("disconnected");
		});
		expect(screen.getByTestId(STATUS_TEST_ID)).toHaveTextContent(
			"disconnected",
		);
	});

	// -----------------------------------------------------------------------
	// Chat callbacks (no-op stubs)
	// -----------------------------------------------------------------------

	it("provides no-op chat callbacks to SSEClient", () => {
		render(
			<SSEProvider>
				<div />
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		const config = mocks.getCapturedConfig()!;

		// Calling chat callbacks should not throw
		expect(() => config.onChatToken("token")).not.toThrow();
		expect(() => config.onChatDone("msg-id")).not.toThrow();
		expect(() => config.onToolStart("search", { q: "test" })).not.toThrow();
		expect(() => config.onToolResult("search", true)).not.toThrow();
	});
});

// ---------------------------------------------------------------------------
// useSSE hook
// ---------------------------------------------------------------------------

describe("useSSE", () => {
	it("returns status from SSEProvider context", () => {
		render(
			<SSEProvider>
				<StatusDisplay />
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		expect(screen.getByTestId(STATUS_TEST_ID)).toHaveTextContent(
			"disconnected",
		);
	});

	it("reflects status changes from onStatusChange", () => {
		render(
			<SSEProvider>
				<StatusDisplay />
			</SSEProvider>,
			{ wrapper: TestWrapper },
		);

		act(() => {
			mocks.getCapturedConfig()!.onStatusChange!("connected");
		});

		expect(screen.getByTestId(STATUS_TEST_ID)).toHaveTextContent("connected");
	});

	it("throws when used outside SSEProvider", () => {
		// Suppress React error boundary console output
		const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

		expect(() => render(<StatusDisplay />, { wrapper: TestWrapper })).toThrow(
			"useSSE must be used within an SSEProvider",
		);

		consoleSpy.mockRestore();
	});
});
