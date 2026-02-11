"use client";

/**
 * Generic drag-and-drop reorderable list component.
 *
 * REQ-012 §7.4: Drag-and-drop reorder for persona collections.
 * REQ-012 §9.2: Resume bullet ordering.
 * REQ-012 §12.2: Job source preferences ordering.
 *
 * Desktop: DndContext + SortableContext with drag handles.
 * Mobile (<768px): Up/down arrow buttons (no DnD context mounted).
 */

import {
	closestCenter,
	DndContext,
	type DragCancelEvent,
	type DragEndEvent,
	type DragOverEvent,
	type DragStartEvent,
	KeyboardSensor,
	PointerSensor,
	useSensor,
	useSensors,
} from "@dnd-kit/core";
import {
	arrayMove,
	SortableContext,
	sortableKeyboardCoordinates,
	useSortable,
	verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ChevronDown, ChevronUp, GripVertical } from "lucide-react";

import { useIsMobile } from "@/hooks/use-is-mobile";
import { cn } from "@/lib/utils";

import { Button } from "./button";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ReorderableItem {
	id: string;
}

export interface ReorderableListProps<T extends ReorderableItem> {
	items: T[];
	onReorder: (reorderedItems: T[]) => void;
	renderItem: (item: T, dragHandle: React.ReactNode | null) => React.ReactNode;
	label: string;
	className?: string;
}

// ---------------------------------------------------------------------------
// Desktop: Sortable item with drag handle
// ---------------------------------------------------------------------------

interface SortableItemProps<T extends ReorderableItem> {
	item: T;
	renderItem: ReorderableListProps<T>["renderItem"];
}

function SortableItem<T extends ReorderableItem>({
	item,
	renderItem,
}: SortableItemProps<T>) {
	const {
		attributes,
		listeners,
		setNodeRef,
		setActivatorNodeRef,
		transform,
		transition,
		isDragging,
	} = useSortable({ id: item.id });

	const style: React.CSSProperties = {
		transform: CSS.Translate.toString(transform),
		transition,
		opacity: isDragging ? 0.5 : undefined,
	};

	const dragHandle = (
		<Button
			ref={setActivatorNodeRef}
			variant="ghost"
			size="icon-xs"
			className="cursor-grab touch-none active:cursor-grabbing"
			aria-label="Drag to reorder"
			{...attributes}
			{...listeners}
		>
			<GripVertical className="size-4" />
		</Button>
	);

	return (
		<li
			ref={setNodeRef}
			style={style}
			data-slot="reorderable-item"
			className="list-none"
		>
			{renderItem(item, dragHandle)}
		</li>
	);
}

// ---------------------------------------------------------------------------
// Mobile: Item with up/down arrow buttons
// ---------------------------------------------------------------------------

interface MobileItemProps<T extends ReorderableItem> {
	item: T;
	index: number;
	total: number;
	onMoveUp: (index: number) => void;
	onMoveDown: (index: number) => void;
	renderItem: ReorderableListProps<T>["renderItem"];
}

function MobileItem<T extends ReorderableItem>({
	item,
	index,
	total,
	onMoveUp,
	onMoveDown,
	renderItem,
}: MobileItemProps<T>) {
	return (
		<li data-slot="reorderable-item" className="list-none">
			<div className="flex items-center gap-1">
				<div className="flex flex-col">
					<Button
						variant="ghost"
						size="icon-xs"
						aria-label="Move up"
						disabled={index === 0}
						onClick={() => onMoveUp(index)}
					>
						<ChevronUp className="size-3" />
					</Button>
					<Button
						variant="ghost"
						size="icon-xs"
						aria-label="Move down"
						disabled={index === total - 1}
						onClick={() => onMoveDown(index)}
					>
						<ChevronDown className="size-3" />
					</Button>
				</div>
				<div className="flex-1">{renderItem(item, null)}</div>
			</div>
		</li>
	);
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ReorderableList<T extends ReorderableItem>({
	items,
	onReorder,
	renderItem,
	label,
	className,
}: ReorderableListProps<T>) {
	const isMobile = useIsMobile();

	const handleMoveUp = (index: number) => {
		if (index <= 0) return;
		onReorder(arrayMove([...items], index, index - 1));
	};

	const handleMoveDown = (index: number) => {
		if (index >= items.length - 1) return;
		onReorder(arrayMove([...items], index, index + 1));
	};

	if (isMobile) {
		return (
			<div data-slot="reorderable-list" className={cn(className)}>
				<ul role="list" aria-label={label} className="flex flex-col gap-2">
					{items.map((item, index) => (
						<MobileItem
							key={item.id}
							item={item}
							index={index}
							total={items.length}
							onMoveUp={handleMoveUp}
							onMoveDown={handleMoveDown}
							renderItem={renderItem}
						/>
					))}
				</ul>
			</div>
		);
	}

	return (
		<DesktopList
			items={items}
			onReorder={onReorder}
			renderItem={renderItem}
			label={label}
			className={className}
		/>
	);
}

// ---------------------------------------------------------------------------
// Desktop list (separated to avoid mounting DndContext on mobile)
// ---------------------------------------------------------------------------

function DesktopList<T extends ReorderableItem>({
	items,
	onReorder,
	renderItem,
	label,
	className,
}: ReorderableListProps<T>) {
	const sensors = useSensors(
		useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
		useSensor(KeyboardSensor, {
			coordinateGetter: sortableKeyboardCoordinates,
		}),
	);

	const handleDragEnd = (event: DragEndEvent) => {
		const { active, over } = event;
		if (!over || active.id === over.id) return;

		const oldIndex = items.findIndex((item) => item.id === active.id);
		const newIndex = items.findIndex((item) => item.id === over.id);
		if (oldIndex === -1 || newIndex === -1) return;

		onReorder(arrayMove([...items], oldIndex, newIndex));
	};

	const announcements = {
		onDragStart({ active }: DragStartEvent) {
			const index = items.findIndex((i) => i.id === active.id);
			return `Picked up item ${index + 1} of ${items.length} in ${label} list`;
		},
		onDragOver({ active, over }: DragOverEvent) {
			if (!over) return "";
			const fromIndex = items.findIndex((i) => i.id === active.id);
			const toIndex = items.findIndex((i) => i.id === over.id);
			return `Item ${fromIndex + 1} moved to position ${toIndex + 1} of ${items.length}`;
		},
		onDragEnd({ over }: DragEndEvent) {
			if (!over) return `Item dropped in original position`;
			const toIndex = items.findIndex((i) => i.id === over.id);
			return `Item dropped at position ${toIndex + 1} of ${items.length}`;
		},
		onDragCancel({ active }: DragCancelEvent) {
			const index = items.findIndex((i) => i.id === active.id);
			return `Dragging cancelled. Item ${index + 1} returned to original position`;
		},
	};

	return (
		<div data-slot="reorderable-list" className={cn(className)}>
			<DndContext
				sensors={sensors}
				collisionDetection={closestCenter}
				onDragEnd={handleDragEnd}
				accessibility={{ announcements }}
			>
				<SortableContext
					items={items.map((item) => item.id)}
					strategy={verticalListSortingStrategy}
				>
					<ul role="list" aria-label={label} className="flex flex-col gap-2">
						{items.map((item) => (
							<SortableItem key={item.id} item={item} renderItem={renderItem} />
						))}
					</ul>
				</SortableContext>
			</DndContext>
		</div>
	);
}
