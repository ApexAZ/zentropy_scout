"""Golden set schema and loader for scoring validation.

REQ-008 §11.2: Validation Approach — Golden Set.

The golden set is a curated collection of 50 Persona/Job pairs with human-labeled
scores used to validate the scoring algorithm's accuracy. The algorithm scores
should correlate with human labels (r > 0.8) to be considered valid.

Usage:
    from app.services.golden_set import load_golden_set

    golden_set = load_golden_set(Path("tests/fixtures/golden_set.json"))
    for entry in golden_set.entries:
        # Run algorithm and compare to entry.human_fit_score, entry.human_stretch_score
        pass
"""

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from app.core.errors import APIError

logger = logging.getLogger(__name__)

# =============================================================================
# Custom Exception
# =============================================================================


class GoldenSetValidationError(APIError):
    """Raised when golden set file is invalid or cannot be loaded."""

    def __init__(self, message: str) -> None:
        super().__init__(
            code="GOLDEN_SET_VALIDATION_ERROR",
            message=message,
            status_code=500,
        )


# =============================================================================
# GoldenSetEntry
# =============================================================================


class GoldenSetEntry(BaseModel):
    """A single Persona/Job pair with human-labeled scores.

    REQ-008 §11.2: Each entry represents one data point in the golden set,
    containing simplified persona and job descriptions along with human-assigned
    Fit and Stretch scores for validation.

    Attributes:
        id: Unique identifier for this entry (e.g., "gs-001").
        persona_summary: Brief description of the persona's key attributes.
        job_summary: Brief description of the job's key requirements.
        human_fit_score: Human-assigned Fit Score (0-100).
        human_stretch_score: Human-assigned Stretch Score (0-100).
        notes: Optional notes explaining the scoring rationale.
    """

    id: str = Field(..., min_length=1, description="Unique entry identifier")
    persona_summary: str = Field(..., description="Brief persona description")
    job_summary: str = Field(..., description="Brief job description")
    human_fit_score: int = Field(
        ..., ge=0, le=100, description="Human-assigned Fit Score (0-100)"
    )
    human_stretch_score: int = Field(
        ..., ge=0, le=100, description="Human-assigned Stretch Score (0-100)"
    )
    notes: str | None = Field(None, description="Optional scoring rationale")


# =============================================================================
# GoldenSetMetadata
# =============================================================================


class GoldenSetMetadata(BaseModel):
    """Metadata about the golden set collection.

    Attributes:
        version: Semantic version of the golden set (e.g., "1.0.0").
        created_date: Date the golden set was created (ISO format).
        last_updated: Date the golden set was last updated (ISO format).
        description: Optional description of the golden set.
        curated_by: Optional name of the person who curated the set.
        target_correlation: Target Pearson correlation coefficient (default 0.8).
    """

    version: str = Field(..., description="Semantic version of the golden set")
    created_date: str = Field(..., description="Creation date (ISO format)")
    last_updated: str | None = Field(None, description="Last update date")
    description: str | None = Field(None, description="Golden set description")
    curated_by: str | None = Field(None, description="Curator name")
    # WHY 0.8: REQ-008 §11.2 specifies r > 0.8 as the target correlation
    target_correlation: float = Field(
        0.8, ge=0.0, le=1.0, description="Target correlation coefficient"
    )


# =============================================================================
# GoldenSet
# =============================================================================


class GoldenSet(BaseModel):
    """Complete golden set collection with metadata and entries.

    REQ-008 §11.2: The golden set should contain ~50 curated Persona/Job pairs
    with human-labeled scores for algorithm validation.

    Attributes:
        metadata: Metadata about the golden set.
        entries: List of Persona/Job pair entries.
    """

    metadata: GoldenSetMetadata
    entries: list[GoldenSetEntry]

    # WHY: Entry ID lookup is O(n) without index. For a 50-entry set this is
    # acceptable, but we cache the index on first access for efficiency.
    _entry_index: dict[str, GoldenSetEntry] = {}

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "GoldenSet":
        """Ensure all entry IDs are unique."""
        ids = [entry.id for entry in self.entries]
        if len(ids) != len(set(ids)):
            duplicates = [id for id in ids if ids.count(id) > 1]
            raise ValueError(f"Duplicate entry IDs found: {set(duplicates)}")
        # Build index for efficient lookup
        self._entry_index = {entry.id: entry for entry in self.entries}
        return self

    @property
    def entry_count(self) -> int:
        """Return the number of entries in the golden set."""
        return len(self.entries)

    def get_entry(self, entry_id: str) -> GoldenSetEntry | None:
        """Retrieve an entry by its ID.

        Args:
            entry_id: The unique ID of the entry to retrieve.

        Returns:
            The entry if found, None otherwise.
        """
        return self._entry_index.get(entry_id)


# =============================================================================
# Loader Function
# =============================================================================


def load_golden_set(file_path: Path) -> GoldenSet:
    """Load a golden set from a JSON file.

    REQ-008 §11.2: Load curated Persona/Job pairs for validation.

    Args:
        file_path: Path to the golden set JSON file.

    Returns:
        Parsed GoldenSet object.

    Raises:
        GoldenSetValidationError: If the file is missing, invalid JSON,
            or fails schema validation.

    Example:
        >>> golden_set = load_golden_set(Path("tests/fixtures/golden_set.json"))
        >>> print(f"Loaded {golden_set.entry_count} entries")
    """
    # Check file exists
    if not file_path.exists():
        logger.error("Golden set file not found: %s", file_path)
        raise GoldenSetValidationError("Golden set file could not be loaded")

    # Load and parse JSON
    try:
        content = file_path.read_text()
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in golden set file: %s", e)
        raise GoldenSetValidationError("Golden set file contains invalid JSON") from e

    # Validate required fields
    if "metadata" not in data:
        raise GoldenSetValidationError(
            "Golden set file missing required 'metadata' field"
        )
    if "entries" not in data:
        raise GoldenSetValidationError(
            "Golden set file missing required 'entries' field"
        )

    # Parse with Pydantic
    try:
        return GoldenSet(**data)
    except ValueError as e:
        logger.error("Golden set validation failed: %s", e)
        raise GoldenSetValidationError("Golden set validation failed") from e
