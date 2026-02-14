/**
 * Types for the deletion reference check system.
 *
 * REQ-012 §7.5 / REQ-001 §7b: Before deleting a persona item, check
 * for references in BaseResumes and CoverLetters, then show the
 * appropriate dialog variant (three-option for mutable refs, block
 * for immutable refs) or delete immediately (no refs).
 */

// ---------------------------------------------------------------------------
// Item types
// ---------------------------------------------------------------------------

/** Persona item types that support reference checking (REQ-001 §7b.1 table). */
export type DeletableItemType =
	| "work-history"
	| "skill"
	| "education"
	| "certification"
	| "achievement-story";

// ---------------------------------------------------------------------------
// Reference check API types
// ---------------------------------------------------------------------------

/** A single entity that references the item being deleted. */
export interface ReferencingEntity {
	id: string;
	name: string;
	type: "base_resume" | "cover_letter";
	immutable: boolean;
	application_id?: string;
	company_name?: string;
}

/** API response from GET /personas/{id}/{collection}/{itemId}/references. */
export interface ReferenceCheckResponse {
	has_references: boolean;
	has_immutable_references: boolean;
	references: ReferencingEntity[];
}

// ---------------------------------------------------------------------------
// Flow state machine
// ---------------------------------------------------------------------------

/** State machine for the deletion flow. */
export type DeleteFlowState =
	| "idle"
	| "checking"
	| "mutable-refs"
	| "immutable-block"
	| "review-each"
	| "deleting";
