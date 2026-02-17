/**
 * Shared column renderers and definitions for application tables.
 *
 * Used by both ApplicationsTable (dashboard tabs) and ApplicationsList
 * (dedicated applications page) to avoid duplicating column definitions.
 */

import type {
	CellContext,
	ColumnDef,
	HeaderContext,
} from "@tanstack/react-table";

import { formatDateTimeAgo } from "@/lib/job-formatters";
import { DataTableColumnHeader } from "@/components/data-table/data-table-column-header";
import { StatusBadge } from "@/components/ui/status-badge";
import type { Application } from "@/types/application";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EM_DASH = "\u2014";

// ---------------------------------------------------------------------------
// Column renderers
// ---------------------------------------------------------------------------

function JobTitleHeader({
	column,
}: Readonly<HeaderContext<Application, unknown>>) {
	return <DataTableColumnHeader column={column} title="Job Title" />;
}

function JobTitleCell({ row }: Readonly<CellContext<Application, unknown>>) {
	return (
		<div>
			<div className="font-medium">{row.original.job_snapshot.title}</div>
			<div className="text-muted-foreground text-sm">
				{row.original.job_snapshot.company_name}
			</div>
		</div>
	);
}

function StatusHeader({
	column,
}: Readonly<HeaderContext<Application, unknown>>) {
	return <DataTableColumnHeader column={column} title="Status" />;
}

function StatusCell({ row }: Readonly<CellContext<Application, unknown>>) {
	return <StatusBadge status={row.original.status} />;
}

function InterviewStageHeader({
	column,
}: Readonly<HeaderContext<Application, unknown>>) {
	return <DataTableColumnHeader column={column} title="Interview Stage" />;
}

function InterviewStageCell({
	row,
}: Readonly<CellContext<Application, unknown>>) {
	const stage = row.original.current_interview_stage;
	if (stage) {
		return (
			<span className="bg-warning/20 text-warning-foreground inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium">
				{stage}
			</span>
		);
	}
	return EM_DASH;
}

function AppliedAtHeader({
	column,
}: Readonly<HeaderContext<Application, unknown>>) {
	return <DataTableColumnHeader column={column} title="Applied" />;
}

function LastUpdatedHeader({
	column,
}: Readonly<HeaderContext<Application, unknown>>) {
	return <DataTableColumnHeader column={column} title="Last Updated" />;
}

// ---------------------------------------------------------------------------
// Column definitions
// ---------------------------------------------------------------------------

/**
 * Base application columns shared by ApplicationsTable and ApplicationsList.
 *
 * Includes: Job Title, Status, Interview Stage, Applied, Last Updated.
 * The ApplicationsList may prepend a select column when in select mode.
 */
const APPLICATION_COLUMNS: ColumnDef<Application, unknown>[] = [
	{
		id: "job_title",
		accessorFn: (row) =>
			`${row.job_snapshot.title} ${row.job_snapshot.company_name}`,
		header: JobTitleHeader,
		cell: JobTitleCell,
		enableSorting: false,
	},
	{
		accessorKey: "status",
		header: StatusHeader,
		cell: StatusCell,
		enableSorting: false,
	},
	{
		id: "interview_stage",
		accessorFn: (row) => row.current_interview_stage,
		header: InterviewStageHeader,
		cell: InterviewStageCell,
		enableSorting: false,
	},
	{
		accessorKey: "applied_at",
		header: AppliedAtHeader,
		cell: ({ row }) => formatDateTimeAgo(row.original.applied_at),
	},
	{
		accessorKey: "status_updated_at",
		header: LastUpdatedHeader,
		cell: ({ row }) => formatDateTimeAgo(row.original.status_updated_at),
	},
];

export { APPLICATION_COLUMNS };
