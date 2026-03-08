"use client";

/**
 * Inline routing test cell — test button + result badge.
 *
 * REQ-028 §6.2: Each row has a test button that sends a test prompt to
 * POST /admin/routing/test with the row's task type.
 */

import { useCallback, useState } from "react";
import { Loader2 } from "lucide-react";

import { testRouting } from "@/lib/api/admin";
import { Button } from "@/components/ui/button";
import type { RoutingTestRequest } from "@/types/admin";

/** Default test prompt sent to the routing test endpoint. */
export const TEST_PROMPT = "Hello, this is a routing test.";

interface TestResult {
	status: "loading" | "success" | "error";
	latencyMs?: number;
	error?: string;
}

interface RoutingTestCellProps {
	taskType: string;
	disabled: boolean;
}

/** Test button + inline result badge for a single routing table row. */
export function RoutingTestCell({ taskType, disabled }: RoutingTestCellProps) {
	const [testResult, setTestResult] = useState<TestResult | null>(null);

	const handleTest = useCallback(async () => {
		setTestResult({ status: "loading" });
		try {
			const body: RoutingTestRequest = {
				task_type: taskType,
				prompt: TEST_PROMPT,
			};
			const result = await testRouting(body);
			setTestResult({
				status: "success",
				latencyMs: result.data.latency_ms,
			});
		} catch (err) {
			const message = err instanceof Error ? err.message : "Test failed";
			setTestResult({ status: "error", error: message });
		}
	}, [taskType]);

	return (
		<div className="flex items-center gap-2" aria-live="polite">
			<Button
				data-testid={`test-btn-${taskType}`}
				variant="outline"
				size="sm"
				disabled={disabled}
				onClick={() => void handleTest()}
			>
				Test
			</Button>
			{testResult?.status === "loading" && (
				<Loader2
					data-testid={`test-loading-${taskType}`}
					className="text-muted-foreground h-4 w-4 animate-spin"
				/>
			)}
			{testResult?.status === "success" && (
				<span
					data-testid={`test-result-${taskType}`}
					className="bg-success/10 text-success inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
				>
					{Math.round(testResult.latencyMs ?? 0)}ms
				</span>
			)}
			{testResult?.status === "error" && (
				<span
					data-testid={`test-result-${taskType}`}
					className="bg-destructive/10 text-destructive inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
				>
					{testResult.error}
				</span>
			)}
		</div>
	);
}
