/**
 * Compact select dropdown for data table toolbars.
 *
 * Wraps the Select/SelectTrigger/SelectContent/SelectItem pattern
 * used across opportunities, applications-list, and applications-table
 * toolbars to eliminate duplicated markup.
 */

import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ToolbarSelectOption {
	readonly value: string;
	readonly label: string;
}

interface ToolbarSelectProps {
	value: string;
	onValueChange: (value: string) => void;
	label: string;
	options: readonly ToolbarSelectOption[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function ToolbarSelect({
	value,
	onValueChange,
	label,
	options,
}: Readonly<ToolbarSelectProps>) {
	return (
		<Select value={value} onValueChange={onValueChange}>
			<SelectTrigger aria-label={label} size="sm">
				<SelectValue />
			</SelectTrigger>
			<SelectContent>
				{options.map((opt) => (
					<SelectItem key={opt.value} value={opt.value}>
						{opt.label}
					</SelectItem>
				))}
			</SelectContent>
		</Select>
	);
}

export { ToolbarSelect };
export type { ToolbarSelectProps, ToolbarSelectOption };
