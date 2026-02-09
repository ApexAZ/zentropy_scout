import { QueryClient, useQueryClient } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { QueryProvider } from "./query-provider";

// ---------------------------------------------------------------------------
// Test constants
// ---------------------------------------------------------------------------

const HAS_CLIENT_TEST_ID = "has-client";
const CLIENT_PRESENT = "yes";

// ---------------------------------------------------------------------------
// Helper — component that reads from query context
// ---------------------------------------------------------------------------

function QueryContextConsumer() {
	const client = useQueryClient();
	return (
		<div data-testid={HAS_CLIENT_TEST_ID}>{client ? CLIENT_PRESENT : "no"}</div>
	);
}

// ---------------------------------------------------------------------------
// QueryProvider — rendering and context
// ---------------------------------------------------------------------------

describe("QueryProvider", () => {
	const clients: QueryClient[] = [];

	afterEach(() => {
		for (const c of clients) {
			c.clear();
		}
		clients.length = 0;
	});

	it("renders children", () => {
		render(
			<QueryProvider>
				<p>hello</p>
			</QueryProvider>,
		);
		expect(screen.getByText("hello")).toBeInTheDocument();
	});

	it("provides a QueryClient to descendants", () => {
		render(
			<QueryProvider>
				<QueryContextConsumer />
			</QueryProvider>,
		);
		expect(screen.getByTestId(HAS_CLIENT_TEST_ID)).toHaveTextContent(
			CLIENT_PRESENT,
		);
	});

	it("accepts a custom QueryClient", () => {
		const custom = new QueryClient({
			defaultOptions: { queries: { retry: 5 } },
		});
		clients.push(custom);

		render(
			<QueryProvider client={custom}>
				<QueryContextConsumer />
			</QueryProvider>,
		);
		expect(screen.getByTestId(HAS_CLIENT_TEST_ID)).toHaveTextContent(
			CLIENT_PRESENT,
		);
	});

	it("uses the provided custom client in context", () => {
		const custom = new QueryClient({
			defaultOptions: { queries: { retry: 99 } },
		});
		clients.push(custom);

		function RetryReader() {
			const client = useQueryClient();
			const retry = client.getDefaultOptions().queries?.retry;
			return <span data-testid="retry">{String(retry)}</span>;
		}

		render(
			<QueryProvider client={custom}>
				<RetryReader />
			</QueryProvider>,
		);
		expect(screen.getByTestId("retry")).toHaveTextContent("99");
	});
});
