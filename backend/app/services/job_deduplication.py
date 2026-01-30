"""Job deduplication service for detecting duplicate postings.

REQ-007 §6.6 + REQ-003 §9: Deduplication logic for job postings.

Deduplication Decision Logic:
    1. Same source + same external_id → update_existing
    2. Different source + same description_hash → add_to_also_found_on
    3. Same company + similar title + >85% similarity → create_linked_repost
    4. No match → create_new

Similar Title Definition (REQ-003 §8.1):
    - Levenshtein distance <= 3 characters, OR
    - One title contains the other, OR
    - Titles share >=80% of words (ignoring order)

Priority Rules for Merging (REQ-003 §9.3):
    - salary: Prefer source that has it
    - apply_url: Prefer company ATS URL over aggregator
    - posted_date: Prefer earliest date found
    - description: Prefer longest/most complete
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Literal

# WHY Any: Job data comes from various sources (API, database, agents) with
# different schemas. Using dict[str, Any] provides flexibility while the
# is_duplicate() function validates required keys exist before use.

# =============================================================================
# Constants
# =============================================================================

# WHY 0.85: REQ-007 §6.6 specifies >85% description similarity for repost detection.
# This threshold balances catching true reposts vs false positives from similar-but-different jobs.
DESCRIPTION_SIMILARITY_THRESHOLD = 0.85

# WHY 3: REQ-003 §8.1 specifies Levenshtein distance <= 3 for similar titles.
# Allows minor typos/numbering differences (e.g., "II" vs "2").
LEVENSHTEIN_THRESHOLD = 3

# WHY 0.80: REQ-003 §8.1 specifies >=80% word overlap for similar titles.
# Allows reordering (e.g., "Agile Coach / Scrum Master" vs "Scrum Master / Agile Coach").
WORD_OVERLAP_THRESHOLD = 0.80

# WHY: Common ATS domains indicate direct company application URLs.
# These are preferred over aggregator redirect URLs per REQ-003 §9.3.
ATS_DOMAINS = (
    "greenhouse.io",
    "lever.co",
    "workday.com",
    "icims.com",
    "taleo.net",
    "ultipro.com",
    "smartrecruiters.com",
    "jobvite.com",
    "myworkdayjobs.com",
    "applytojob.com",
    "ashbyhq.com",
)

# WHY: Aggregator domains use redirect URLs that may break or track users.
# These are deprioritized in favor of direct ATS URLs.
AGGREGATOR_DOMAINS = (
    "adzuna.com",
    "indeed.com",
    "linkedin.com",
    "remoteok.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "monster.com",
    "careerbuilder.com",
)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class DuplicateResult:
    """Result of deduplication check.

    REQ-007 §6.6: Encapsulates the deduplication decision.

    Attributes:
        action: The deduplication action to take.
        matched_job_id: ID of the matched existing job, or None for create_new.
    """

    action: Literal[
        "update_existing",
        "add_to_also_found_on",
        "create_linked_repost",
        "create_new",
    ]
    matched_job_id: str | None


# =============================================================================
# Title Similarity Functions (REQ-003 §8.1)
# =============================================================================


def _normalize_title(title: str) -> str:
    """Normalize title for comparison.

    Args:
        title: Raw job title.

    Returns:
        Lowercase title with normalized whitespace and punctuation removed.
    """
    # Lowercase and strip
    normalized = title.lower().strip()
    # Remove all punctuation (including hyphens surrounded by spaces like " - ")
    # WHY: Punctuation variations like "/" vs "-" shouldn't affect similarity.
    # "Agile Coach / Scrum Master" and "Agile Coach - Scrum Master" are equivalent.
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    # Normalize whitespace
    normalized = " ".join(normalized.split())
    return normalized


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein edit distance between two strings.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Minimum number of single-character edits to transform s1 into s2.
    """
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost is 0 if characters match, 1 otherwise
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def _word_overlap_ratio(title1: str, title2: str) -> float:
    """Calculate word overlap ratio between two titles.

    Args:
        title1: First title (normalized).
        title2: Second title (normalized).

    Returns:
        Ratio of shared words to total unique words (0.0 to 1.0).
    """
    words1 = set(title1.split())
    words2 = set(title2.split())

    all_words = words1 | words2
    if not all_words:
        # Both titles are empty or whitespace-only
        return 0.0

    shared_words = words1 & words2
    return len(shared_words) / len(all_words)


def is_similar_title(title1: str, title2: str) -> bool:
    """Check if two job titles are similar.

    REQ-003 §8.1: Similar title definition.

    A title is similar if any of:
    - Levenshtein distance <= 3 characters
    - One title contains the other
    - Titles share >=80% of words (ignoring order)

    Args:
        title1: First job title.
        title2: Second job title.

    Returns:
        True if titles are considered similar, False otherwise.
    """
    # Handle empty titles
    if not title1 or not title2:
        return False

    # Normalize for comparison
    norm1 = _normalize_title(title1)
    norm2 = _normalize_title(title2)

    if not norm1 or not norm2:
        return False

    # Check 1: Exact match (common case, fast check)
    if norm1 == norm2:
        return True

    # Check 2: One contains the other
    if norm1 in norm2 or norm2 in norm1:
        return True

    # Check 3: Levenshtein distance <= 3
    if _levenshtein_distance(norm1, norm2) <= LEVENSHTEIN_THRESHOLD:
        return True

    # Check 4: Word overlap >= 80%
    return _word_overlap_ratio(norm1, norm2) >= WORD_OVERLAP_THRESHOLD


# =============================================================================
# Description Similarity Functions
# =============================================================================


def calculate_description_similarity(desc1: str, desc2: str) -> float:
    """Calculate similarity ratio between two job descriptions.

    REQ-007 §6.6: Uses 85% threshold for repost detection.

    Args:
        desc1: First job description.
        desc2: Second job description.

    Returns:
        Similarity ratio from 0.0 to 1.0.
    """
    # Handle empty descriptions
    # WHY 1.0 for both empty: Two jobs with no description text are technically
    # identical in content (both have nothing). This is an edge case that
    # shouldn't occur in practice since job postings always have descriptions.
    if not desc1 and not desc2:
        return 1.0
    if not desc1 or not desc2:
        return 0.0  # One empty = no similarity

    # Normalize whitespace for fair comparison
    norm1 = " ".join(desc1.split())
    norm2 = " ".join(desc2.split())

    # Use SequenceMatcher for similarity ratio
    # WHY SequenceMatcher: Handles insertions/deletions well, which is common
    # in reposts where companies add/remove dates or minor details.
    return SequenceMatcher(None, norm1, norm2).ratio()


# =============================================================================
# Main Deduplication Logic (REQ-007 §6.6)
# =============================================================================


def is_duplicate(
    new_job: dict[str, Any],
    existing_jobs: list[dict[str, Any]],
) -> DuplicateResult:
    """Determine if a new job is a duplicate of an existing one.

    REQ-007 §6.6: Deduplication decision logic.

    Priority order:
    1. Same source + same external_id → update_existing
    2. Same description_hash (any source) → add_to_also_found_on
    3. Same company + similar title + >85% description similarity → create_linked_repost
    4. No match → create_new

    Args:
        new_job: New job posting dict with keys:
            - source_id: Source identifier
            - external_id: Source-specific job ID
            - company_name: Company name
            - job_title: Job title
            - description: Full job description
            - description_hash: Hash of description for exact matching
        existing_jobs: List of existing job dicts with same keys plus 'id'.

    Returns:
        DuplicateResult with action and matched_job_id.
    """
    if not existing_jobs:
        return DuplicateResult(action="create_new", matched_job_id=None)

    new_source_id = new_job.get("source_id")
    new_external_id = new_job.get("external_id")
    new_description_hash = new_job.get("description_hash")
    new_company = (new_job.get("company_name") or "").lower().strip()
    new_title = new_job.get("job_title") or ""
    new_description = new_job.get("description") or ""

    # Check 1: Same source + same external_id (highest priority)
    for existing in existing_jobs:
        if (
            existing.get("source_id") == new_source_id
            and existing.get("external_id") == new_external_id
        ):
            return DuplicateResult(
                action="update_existing",
                matched_job_id=existing.get("id"),
            )

    # Check 2: Same description_hash (cross-source duplicate)
    for existing in existing_jobs:
        if existing.get("description_hash") == new_description_hash:
            return DuplicateResult(
                action="add_to_also_found_on",
                matched_job_id=existing.get("id"),
            )

    # Check 3: Same company + similar title + >85% description similarity (repost)
    for existing in existing_jobs:
        existing_company = (existing.get("company_name") or "").lower().strip()
        existing_title = existing.get("job_title") or ""
        existing_description = existing.get("description") or ""

        # Must be same company (case-insensitive)
        if existing_company != new_company:
            continue

        # Must have similar title
        if not is_similar_title(new_title, existing_title):
            continue

        # Must have >85% description similarity
        similarity = calculate_description_similarity(
            new_description, existing_description
        )
        if similarity > DESCRIPTION_SIMILARITY_THRESHOLD:
            return DuplicateResult(
                action="create_linked_repost",
                matched_job_id=existing.get("id"),
            )

    # No match found
    return DuplicateResult(action="create_new", matched_job_id=None)


# =============================================================================
# Data Merging Functions (REQ-003 §9.3)
# =============================================================================


def _is_ats_url(url: str | None) -> bool:
    """Check if URL is from a known ATS (Applicant Tracking System).

    Args:
        url: URL to check.

    Returns:
        True if URL appears to be from an ATS, False otherwise.
    """
    if not url:
        return False
    url_lower = url.lower()
    return any(domain in url_lower for domain in ATS_DOMAINS)


def _is_aggregator_url(url: str | None) -> bool:
    """Check if URL is from a job aggregator.

    Args:
        url: URL to check.

    Returns:
        True if URL appears to be from an aggregator, False otherwise.
    """
    if not url:
        return False
    url_lower = url.lower()
    return any(domain in url_lower for domain in AGGREGATOR_DOMAINS)


def merge_job_data(
    existing: dict[str, Any],
    new: dict[str, Any],
) -> dict[str, Any]:
    """Merge job data from two sources using priority rules.

    REQ-003 §9.3: Priority rules for merging data from multiple sources.

    Priority rules:
    - salary_min/salary_max: Prefer source that has it
    - apply_url: Prefer company ATS URL over aggregator
    - posted_date: Prefer earliest date found
    - description: Prefer longest/most complete

    Args:
        existing: Existing job data dict.
        new: New job data dict to merge.

    Returns:
        Merged job data dict.
    """
    # Start with existing data
    merged = existing.copy()

    # Salary: Prefer source that has it
    if new.get("salary_min") is not None and existing.get("salary_min") is None:
        merged["salary_min"] = new["salary_min"]
    if new.get("salary_max") is not None and existing.get("salary_max") is None:
        merged["salary_max"] = new["salary_max"]

    # Apply URL: Prefer ATS over aggregator
    existing_url = existing.get("apply_url")
    new_url = new.get("apply_url")

    if new_url and (
        # If new is ATS and existing is not ATS, prefer new
        (_is_ats_url(new_url) and not _is_ats_url(existing_url))
        # If existing is aggregator and new is not aggregator, prefer new
        or (_is_aggregator_url(existing_url) and not _is_aggregator_url(new_url))
        # If existing is empty, use new
        or not existing_url
    ):
        merged["apply_url"] = new_url

    # Posted date: Prefer earliest
    existing_date = existing.get("posted_date")
    new_date = new.get("posted_date")

    if new_date and existing_date:
        # Compare as strings (ISO format sorts correctly)
        if new_date < existing_date:
            merged["posted_date"] = new_date
    elif new_date and not existing_date:
        merged["posted_date"] = new_date

    # Description: Prefer longest
    existing_desc = existing.get("description") or ""
    new_desc = new.get("description") or ""

    if len(new_desc) > len(existing_desc):
        merged["description"] = new_desc

    return merged
