"""Tests for job deduplication service.

REQ-007 §6.6 + REQ-003 §9: Deduplication Logic tests.

Tests verify:
- is_duplicate() return values: update_existing, add_to_also_found_on,
  create_linked_repost, create_new
- is_similar_title() per REQ-003 §8.1 (Levenshtein, contains, word overlap)
- description_similarity() for >85% threshold
- also_found_on JSONB structure per REQ-003 §9.2
- Priority rules for merging data per REQ-003 §9.3
- Repost agent context message generation per REQ-003 §8.3
"""

from datetime import UTC, datetime

from app.services.job_deduplication import (
    PriorApplicationContext,
    calculate_description_similarity,
    generate_repost_context_message,
    is_duplicate,
    is_similar_title,
    merge_job_data,
    prepare_repost_data,
    prepare_same_source_update,
)

# =============================================================================
# Similar Title Tests (REQ-003 §8.1)
# =============================================================================


class TestIsSimilarTitle:
    """Tests for is_similar_title() function.

    REQ-003 §8.1: Similar title matching via:
    - Levenshtein distance <= 3 characters
    - One title contains the other
    - Titles share >=80% of words (ignoring order)
    """

    def test_exact_match_returns_true(self) -> None:
        """Exact title match returns True."""
        assert is_similar_title("Scrum Master", "Scrum Master") is True

    def test_case_insensitive_match_returns_true(self) -> None:
        """Title matching is case-insensitive."""
        assert is_similar_title("Scrum Master", "scrum master") is True
        assert is_similar_title("SCRUM MASTER", "Scrum Master") is True

    def test_contains_returns_true(self) -> None:
        """One title containing the other returns True."""
        assert is_similar_title("Senior Scrum Master", "Scrum Master") is True
        assert is_similar_title("Scrum Master", "Senior Scrum Master") is True
        assert is_similar_title("Lead Scrum Master II", "Scrum Master") is True

    def test_levenshtein_distance_3_or_less_returns_true(self) -> None:
        """Levenshtein distance <= 3 returns True."""
        # 1 character difference
        assert is_similar_title("Scrum Master", "Scrum Masters") is True
        # 2 character difference (numeral swap)
        assert is_similar_title("Scrum Master II", "Scrum Master 2") is True
        # 3 character difference
        assert is_similar_title("Dev Engineer", "Dev Engineers") is True

    def test_word_overlap_80_percent_returns_true(self) -> None:
        """Titles sharing >=80% of words returns True."""
        # 100% word overlap, different order
        assert (
            is_similar_title("Agile Coach / Scrum Master", "Scrum Master / Agile Coach")
            is True
        )
        # Same words, punctuation difference
        assert is_similar_title("Scrum Master - Remote", "Remote Scrum Master") is True

    def test_different_titles_returns_false(self) -> None:
        """Different titles return False."""
        assert is_similar_title("Scrum Master", "Product Owner") is False
        assert is_similar_title("Software Engineer", "Data Scientist") is False
        assert is_similar_title("QA Engineer", "DevOps Engineer") is False

    def test_similar_but_different_role_returns_false(self) -> None:
        """Titles with same words but different roles return False."""
        # Only 50% word overlap
        assert is_similar_title("Junior Developer", "Senior Manager") is False

    def test_empty_titles_returns_false(self) -> None:
        """Empty titles return False."""
        assert is_similar_title("", "Scrum Master") is False
        assert is_similar_title("Scrum Master", "") is False
        assert is_similar_title("", "") is False

    def test_whitespace_normalized(self) -> None:
        """Extra whitespace is normalized before comparison."""
        assert is_similar_title("  Scrum  Master  ", "Scrum Master") is True


# =============================================================================
# Description Similarity Tests
# =============================================================================


class TestDescriptionSimilarity:
    """Tests for calculate_description_similarity() function.

    REQ-007 §6.6: Uses 85% threshold for repost detection.
    """

    def test_identical_descriptions_returns_1(self) -> None:
        """Identical descriptions return 1.0."""
        desc = "We are looking for a talented software engineer..."
        assert calculate_description_similarity(desc, desc) == 1.0

    def test_completely_different_returns_low_score(self) -> None:
        """Completely different descriptions return low similarity."""
        desc1 = "Looking for a Python developer with Django experience."
        desc2 = "Join our marketing team as a brand strategist."
        similarity = calculate_description_similarity(desc1, desc2)
        # WHY 0.35: SequenceMatcher finds some common words ("for", "a", etc.)
        # even in unrelated descriptions. Under 35% is still "low similarity".
        assert similarity < 0.35

    def test_similar_descriptions_above_threshold(self) -> None:
        """Similar descriptions (minor changes) score above 85%."""
        desc1 = (
            "We are looking for a talented Software Engineer to join our team. "
            "Requirements: 5+ years Python, Django, PostgreSQL."
        )
        desc2 = (
            "We are looking for a talented Software Engineer to join our team. "
            "Requirements: 5+ years Python, Django, MySQL."
        )
        similarity = calculate_description_similarity(desc1, desc2)
        assert similarity > 0.85

    def test_repost_with_date_change_above_threshold(self) -> None:
        """Repost with only date changed scores above 85%."""
        desc1 = (
            "Posted January 2025. We need a Product Manager to lead our team. "
            "5 years experience required. Remote friendly."
        )
        desc2 = (
            "Posted February 2025. We need a Product Manager to lead our team. "
            "5 years experience required. Remote friendly."
        )
        similarity = calculate_description_similarity(desc1, desc2)
        assert similarity > 0.85

    def test_empty_descriptions_returns_1(self) -> None:
        """Empty descriptions return 1.0 (both are identical)."""
        assert calculate_description_similarity("", "") == 1.0

    def test_one_empty_returns_0(self) -> None:
        """One empty description returns 0.0."""
        assert calculate_description_similarity("", "Some text") == 0.0
        assert calculate_description_similarity("Some text", "") == 0.0

    def test_whitespace_normalized(self) -> None:
        """Whitespace differences don't affect similarity."""
        desc1 = "Software  Engineer   with  Python"
        desc2 = "Software Engineer with Python"
        assert calculate_description_similarity(desc1, desc2) > 0.9


# =============================================================================
# is_duplicate() Tests (REQ-007 §6.6)
# =============================================================================


class TestIsDuplicate:
    """Tests for is_duplicate() function.

    REQ-007 §6.6: Deduplication decision logic.

    Returns one of:
    - "update_existing": Same source + same external_id
    - "add_to_also_found_on": Different source + same description_hash
    - "create_linked_repost": Same company + similar title + >85% similarity
    - "create_new": No match found
    """

    def test_same_source_same_external_id_returns_update_existing(self) -> None:
        """Same source and external_id returns update_existing."""
        new_job = {
            "source_id": "source-123",
            "external_id": "job-456",
            "company_name": "Acme Corp",
            "job_title": "Software Engineer",
            "description": "New description text...",
            "description_hash": "abc123",
        }
        existing_jobs = [
            {
                "id": "existing-id",
                "source_id": "source-123",
                "external_id": "job-456",
                "company_name": "Acme Corp",
                "job_title": "Software Engineer",
                "description": "Old description text...",
                "description_hash": "xyz789",
            }
        ]

        result = is_duplicate(new_job, existing_jobs)

        assert result.action == "update_existing"
        assert result.matched_job_id == "existing-id"

    def test_same_description_hash_different_source_returns_also_found_on(
        self,
    ) -> None:
        """Same description_hash from different source returns add_to_also_found_on."""
        new_job = {
            "source_id": "linkedin-source",
            "external_id": "linkedin-job-789",
            "company_name": "Acme Corp",
            "job_title": "Software Engineer",
            "description": "We are looking for a talented engineer...",
            "description_hash": "same-hash-abc",
        }
        existing_jobs = [
            {
                "id": "existing-id",
                "source_id": "adzuna-source",
                "external_id": "adzuna-job-123",
                "company_name": "Acme Corp",
                "job_title": "Software Engineer",
                "description": "We are looking for a talented engineer...",
                "description_hash": "same-hash-abc",
            }
        ]

        result = is_duplicate(new_job, existing_jobs)

        assert result.action == "add_to_also_found_on"
        assert result.matched_job_id == "existing-id"

    def test_same_company_similar_title_high_similarity_returns_linked_repost(
        self,
    ) -> None:
        """Same company + similar title + >85% similarity returns create_linked_repost."""
        base_desc = (
            "We are hiring a talented Software Engineer to join our team. "
            "Requirements: 5 years experience with Python, Django, PostgreSQL. "
            "Benefits include health insurance, 401k, remote work options."
        )
        repost_desc = (
            "We are hiring a talented Software Engineer to join our team. "
            "Requirements: 5 years experience with Python, Django, PostgreSQL. "
            "Benefits include health insurance, 401k, remote work options. "
            "Updated January 2025."
        )

        new_job = {
            "source_id": "source-123",
            "external_id": "new-job-999",
            "company_name": "Acme Corp",
            "job_title": "Senior Software Engineer",
            "description": repost_desc,
            "description_hash": "new-hash-xyz",
        }
        existing_jobs = [
            {
                "id": "existing-id",
                "source_id": "source-123",
                "external_id": "old-job-111",
                "company_name": "Acme Corp",
                "job_title": "Software Engineer",
                "description": base_desc,
                "description_hash": "old-hash-abc",
            }
        ]

        result = is_duplicate(new_job, existing_jobs)

        assert result.action == "create_linked_repost"
        assert result.matched_job_id == "existing-id"

    def test_different_everything_returns_create_new(self) -> None:
        """No match found returns create_new."""
        new_job = {
            "source_id": "source-123",
            "external_id": "new-job-999",
            "company_name": "NewCo Inc",
            "job_title": "Data Scientist",
            "description": "We need a data scientist for ML projects...",
            "description_hash": "unique-hash-111",
        }
        existing_jobs = [
            {
                "id": "existing-id",
                "source_id": "source-456",
                "external_id": "other-job-222",
                "company_name": "OtherCorp",
                "job_title": "Software Engineer",
                "description": "Looking for a backend developer...",
                "description_hash": "different-hash-222",
            }
        ]

        result = is_duplicate(new_job, existing_jobs)

        assert result.action == "create_new"
        assert result.matched_job_id is None

    def test_empty_existing_jobs_returns_create_new(self) -> None:
        """No existing jobs returns create_new."""
        new_job = {
            "source_id": "source-123",
            "external_id": "job-456",
            "company_name": "Acme Corp",
            "job_title": "Software Engineer",
            "description": "Description...",
            "description_hash": "hash-abc",
        }

        result = is_duplicate(new_job, [])

        assert result.action == "create_new"
        assert result.matched_job_id is None

    def test_priority_same_source_over_description_hash(self) -> None:
        """Same source + external_id takes priority over description_hash match."""
        new_job = {
            "source_id": "source-123",
            "external_id": "job-456",
            "company_name": "Acme Corp",
            "job_title": "Software Engineer",
            "description": "Description text...",
            "description_hash": "hash-abc",
        }
        existing_jobs = [
            {
                "id": "same-source-id",
                "source_id": "source-123",
                "external_id": "job-456",
                "company_name": "Acme Corp",
                "job_title": "Software Engineer",
                "description": "Old description...",
                "description_hash": "different-hash",
            },
            {
                "id": "same-hash-id",
                "source_id": "other-source",
                "external_id": "other-job",
                "company_name": "Acme Corp",
                "job_title": "Software Engineer",
                "description": "Description text...",
                "description_hash": "hash-abc",
            },
        ]

        result = is_duplicate(new_job, existing_jobs)

        # Same source + external_id takes priority
        assert result.action == "update_existing"
        assert result.matched_job_id == "same-source-id"

    def test_priority_description_hash_over_similarity(self) -> None:
        """Description hash match takes priority over similarity match."""
        base_desc = "Looking for a software engineer with 5 years experience."

        new_job = {
            "source_id": "source-123",
            "external_id": "new-job-999",
            "company_name": "Acme Corp",
            "job_title": "Software Engineer",
            "description": base_desc,
            "description_hash": "hash-abc",
        }
        existing_jobs = [
            {
                "id": "hash-match-id",
                "source_id": "other-source",
                "external_id": "other-job",
                "company_name": "Different Corp",
                "job_title": "Different Title",
                "description": "Different description",
                "description_hash": "hash-abc",
            },
            {
                "id": "similarity-match-id",
                "source_id": "source-123",
                "external_id": "old-job-111",
                "company_name": "Acme Corp",
                "job_title": "Software Engineer",
                "description": base_desc + " Updated.",
                "description_hash": "different-hash",
            },
        ]

        result = is_duplicate(new_job, existing_jobs)

        # Description hash takes priority over similarity
        assert result.action == "add_to_also_found_on"
        assert result.matched_job_id == "hash-match-id"

    def test_case_insensitive_company_name(self) -> None:
        """Company name comparison is case-insensitive."""
        base_desc = (
            "We are hiring a talented Software Engineer. "
            "Requirements: Python, Django. "
            "Remote work available."
        )
        new_job = {
            "source_id": "source-123",
            "external_id": "new-job-999",
            "company_name": "ACME CORP",
            "job_title": "Software Engineer",
            "description": base_desc + " Updated.",
            "description_hash": "new-hash",
        }
        existing_jobs = [
            {
                "id": "existing-id",
                "source_id": "source-123",
                "external_id": "old-job-111",
                "company_name": "Acme Corp",
                "job_title": "Software Engineer",
                "description": base_desc,
                "description_hash": "old-hash",
            }
        ]

        result = is_duplicate(new_job, existing_jobs)

        # Should still match due to case-insensitive company comparison
        assert result.action == "create_linked_repost"


# =============================================================================
# Data Merging Tests (REQ-003 §9.3)
# =============================================================================


class TestMergeJobData:
    """Tests for merge_job_data() function.

    REQ-003 §9.3: Priority rules for merging data from multiple sources.
    """

    def test_prefer_salary_when_present(self) -> None:
        """Prefer source that has salary data."""
        existing = {
            "salary_min": None,
            "salary_max": None,
            "job_title": "Software Engineer",
        }
        new = {
            "salary_min": 100000,
            "salary_max": 150000,
            "job_title": "Software Engineer",
        }

        merged = merge_job_data(existing, new)

        assert merged["salary_min"] == 100000
        assert merged["salary_max"] == 150000

    def test_keep_existing_salary_if_new_missing(self) -> None:
        """Keep existing salary if new source doesn't have it."""
        existing = {
            "salary_min": 100000,
            "salary_max": 150000,
            "job_title": "Software Engineer",
        }
        new = {
            "salary_min": None,
            "salary_max": None,
            "job_title": "Software Engineer",
        }

        merged = merge_job_data(existing, new)

        assert merged["salary_min"] == 100000
        assert merged["salary_max"] == 150000

    def test_prefer_company_ats_url_over_aggregator(self) -> None:
        """Prefer company ATS URL over aggregator redirect URL."""
        existing = {
            "apply_url": "https://adzuna.com/redirect?job=123",
            "job_title": "Software Engineer",
        }
        new = {
            "apply_url": "https://acmecorp.greenhouse.io/jobs/123",
            "job_title": "Software Engineer",
        }

        merged = merge_job_data(existing, new)

        # ATS URL (greenhouse.io) preferred over aggregator (adzuna.com/redirect)
        assert merged["apply_url"] == "https://acmecorp.greenhouse.io/jobs/123"

    def test_keep_ats_url_if_new_is_aggregator(self) -> None:
        """Keep existing ATS URL if new source has aggregator URL."""
        existing = {
            "apply_url": "https://acmecorp.lever.co/jobs/123",
            "job_title": "Software Engineer",
        }
        new = {
            "apply_url": "https://remoteok.com/jobs/123",
            "job_title": "Software Engineer",
        }

        merged = merge_job_data(existing, new)

        # Keep existing Lever (ATS) URL
        assert merged["apply_url"] == "https://acmecorp.lever.co/jobs/123"

    def test_prefer_earliest_posted_date(self) -> None:
        """Prefer earliest posted_date found."""
        existing = {"posted_date": "2025-01-20", "job_title": "Software Engineer"}
        new = {"posted_date": "2025-01-15", "job_title": "Software Engineer"}

        merged = merge_job_data(existing, new)

        assert merged["posted_date"] == "2025-01-15"

    def test_keep_earlier_date_if_new_is_later(self) -> None:
        """Keep existing posted_date if new is later."""
        existing = {"posted_date": "2025-01-10", "job_title": "Software Engineer"}
        new = {"posted_date": "2025-01-25", "job_title": "Software Engineer"}

        merged = merge_job_data(existing, new)

        assert merged["posted_date"] == "2025-01-10"

    def test_prefer_longer_description(self) -> None:
        """Prefer longer/more complete description."""
        existing = {
            "description": "Short description.",
            "job_title": "Software Engineer",
        }
        new = {
            "description": "This is a much longer and more detailed description "
            "with requirements and benefits listed.",
            "job_title": "Software Engineer",
        }

        merged = merge_job_data(existing, new)

        assert "much longer" in merged["description"]

    def test_keep_longer_description_if_new_is_shorter(self) -> None:
        """Keep existing description if it's longer."""
        existing = {
            "description": "This is a detailed description with many requirements "
            "and qualifications listed for the position.",
            "job_title": "Software Engineer",
        }
        new = {"description": "Brief desc.", "job_title": "Software Engineer"}

        merged = merge_job_data(existing, new)

        assert "detailed description" in merged["description"]

    def test_merge_preserves_non_priority_fields(self) -> None:
        """Fields not in priority rules are preserved from existing."""
        existing = {
            "job_title": "Software Engineer",
            "company_name": "Acme Corp",
            "location": "Remote",
            "source_id": "source-123",
        }
        new = {
            "job_title": "Software Engineer",
            "company_name": "Acme Corp",
            "location": "New York",
            "source_id": "source-456",
        }

        merged = merge_job_data(existing, new)

        # Non-priority fields preserved from existing
        assert merged["source_id"] == "source-123"
        assert merged["location"] == "Remote"


# =============================================================================
# Repost Confidence Level Tests (REQ-003 §8.1)
# =============================================================================


class TestRepostConfidenceLevels:
    """Tests for repost detection confidence levels.

    REQ-003 §8.1: Three confidence levels for identifying reposts:
    - High: Same source + same external_id, OR same company + similar title + >85% similarity
    - Medium: Same company + similar title + 70-85% similarity
    - None: No match found
    """

    def test_confidence_is_high_when_exact_source_match(self) -> None:
        """Same source + same external_id returns High confidence."""
        new_job = {
            "source_id": "source-123",
            "external_id": "job-456",
            "company_name": "Acme Corp",
            "job_title": "Software Engineer",
            "description": "Description text...",
            "description_hash": "hash-abc",
        }
        existing_jobs = [
            {
                "id": "existing-id",
                "source_id": "source-123",
                "external_id": "job-456",
                "company_name": "Acme Corp",
                "job_title": "Software Engineer",
                "description": "Old description...",
                "description_hash": "different-hash",
            }
        ]

        result = is_duplicate(new_job, existing_jobs)

        assert result.confidence == "High"

    def test_confidence_is_high_when_description_similarity_above_85(self) -> None:
        """Same company + similar title + >85% similarity returns High confidence."""
        base_desc = (
            "We are hiring a talented Software Engineer to join our team. "
            "Requirements: 5 years experience with Python, Django, PostgreSQL. "
            "Benefits include health insurance, 401k, remote work options."
        )
        # Minor change keeps >85% similarity
        repost_desc = base_desc + " Apply today!"

        new_job = {
            "source_id": "source-123",
            "external_id": "new-job-999",
            "company_name": "Acme Corp",
            "job_title": "Software Engineer",
            "description": repost_desc,
            "description_hash": "new-hash",
        }
        existing_jobs = [
            {
                "id": "existing-id",
                "source_id": "source-123",
                "external_id": "old-job-111",
                "company_name": "Acme Corp",
                "job_title": "Software Engineer",
                "description": base_desc,
                "description_hash": "old-hash",
            }
        ]

        result = is_duplicate(new_job, existing_jobs)

        assert result.action == "create_linked_repost"
        assert result.confidence == "High"

    def test_confidence_is_medium_when_description_similarity_between_70_and_85(
        self,
    ) -> None:
        """Same company + similar title + 70-85% similarity returns Medium confidence."""
        # Descriptions that are ~75% similar (moderate changes)
        base_desc = (
            "We are looking for a Software Engineer to join our team. "
            "Requirements: Python, Django, PostgreSQL experience required."
        )
        modified_desc = (
            "We are looking for a Software Engineer to join our team. "
            "Requirements: Python, Flask, MySQL experience required. "
            "This is a remote-first position with flexible hours."
        )

        new_job = {
            "source_id": "source-123",
            "external_id": "new-job-999",
            "company_name": "Acme Corp",
            "job_title": "Software Engineer",
            "description": modified_desc,
            "description_hash": "new-hash",
        }
        existing_jobs = [
            {
                "id": "existing-id",
                "source_id": "source-123",
                "external_id": "old-job-111",
                "company_name": "Acme Corp",
                "job_title": "Software Engineer",
                "description": base_desc,
                "description_hash": "old-hash",
            }
        ]

        result = is_duplicate(new_job, existing_jobs)

        assert result.action == "create_linked_repost"
        assert result.confidence == "Medium"

    def test_confidence_is_none_when_similarity_below_70(self) -> None:
        """Similarity below 70% returns None confidence and create_new action."""
        new_job = {
            "source_id": "source-123",
            "external_id": "new-job-999",
            "company_name": "Acme Corp",
            "job_title": "Software Engineer",
            "description": "Looking for a backend developer with Java Spring Boot.",
            "description_hash": "new-hash",
        }
        existing_jobs = [
            {
                "id": "existing-id",
                "source_id": "source-123",
                "external_id": "old-job-111",
                "company_name": "Acme Corp",
                "job_title": "Software Engineer",
                "description": "We need a frontend engineer skilled in React and TypeScript.",
                "description_hash": "old-hash",
            }
        ]

        result = is_duplicate(new_job, existing_jobs)

        assert result.action == "create_new"
        assert result.confidence is None

    def test_confidence_is_high_when_same_description_hash(self) -> None:
        """Same description_hash from different source returns High confidence."""
        new_job = {
            "source_id": "linkedin-source",
            "external_id": "linkedin-job-789",
            "company_name": "Acme Corp",
            "job_title": "Software Engineer",
            "description": "Same description text...",
            "description_hash": "same-hash-abc",
        }
        existing_jobs = [
            {
                "id": "existing-id",
                "source_id": "adzuna-source",
                "external_id": "adzuna-job-123",
                "company_name": "Acme Corp",
                "job_title": "Software Engineer",
                "description": "Same description text...",
                "description_hash": "same-hash-abc",
            }
        ]

        result = is_duplicate(new_job, existing_jobs)

        assert result.action == "add_to_also_found_on"
        assert result.confidence == "High"

    def test_confidence_is_none_when_create_new(self) -> None:
        """No match returns None confidence."""
        new_job = {
            "source_id": "source-123",
            "external_id": "new-job-999",
            "company_name": "NewCo Inc",
            "job_title": "Data Scientist",
            "description": "ML engineering role...",
            "description_hash": "unique-hash",
        }

        result = is_duplicate(new_job, [])

        assert result.action == "create_new"
        assert result.confidence is None


# =============================================================================
# Repost Handling Tests (REQ-003 §8.2)
# =============================================================================


class TestPrepareRepostData:
    """Tests for prepare_repost_data() function.

    REQ-003 §8.2: When a repost is detected, the system:
    - Creates new Job Posting record with status = Discovered
    - Links via previous_posting_ids
    - Increments repost_count
    - Prepares data for ghost_score recalculation
    """

    def test_status_is_discovered_when_repost_prepared(self) -> None:
        """New repost record has status = Discovered."""
        new_job = {
            "job_title": "Software Engineer",
            "company_name": "Acme Corp",
            "description": "Job description...",
        }
        matched_job = {
            "id": "matched-job-id",
            "repost_count": 0,
            "previous_posting_ids": None,
        }

        result = prepare_repost_data(new_job, matched_job)

        assert result["status"] == "Discovered"

    def test_previous_posting_ids_contains_matched_job_id_when_repost_prepared(
        self,
    ) -> None:
        """New repost links to matched job via previous_posting_ids."""
        new_job = {
            "job_title": "Software Engineer",
            "company_name": "Acme Corp",
            "description": "Job description...",
        }
        matched_job = {
            "id": "matched-job-id",
            "repost_count": 0,
            "previous_posting_ids": None,
        }

        result = prepare_repost_data(new_job, matched_job)

        assert "matched-job-id" in result["previous_posting_ids"]

    def test_previous_posting_ids_includes_prior_chain_when_matched_has_history(
        self,
    ) -> None:
        """New repost includes the matched job's prior posting chain."""
        new_job = {
            "job_title": "Software Engineer",
            "company_name": "Acme Corp",
            "description": "Job description...",
        }
        matched_job = {
            "id": "matched-job-id",
            "repost_count": 2,
            "previous_posting_ids": ["older-job-1", "older-job-2"],
        }

        result = prepare_repost_data(new_job, matched_job)

        # Should include matched job + its prior chain in order
        assert result["previous_posting_ids"] == [
            "matched-job-id",
            "older-job-1",
            "older-job-2",
        ]

    def test_repost_count_increments_when_matched_has_existing_count(self) -> None:
        """repost_count is matched job's count + 1."""
        new_job = {
            "job_title": "Software Engineer",
            "company_name": "Acme Corp",
            "description": "Job description...",
        }
        matched_job = {
            "id": "matched-job-id",
            "repost_count": 2,
            "previous_posting_ids": ["older-1", "older-2"],
        }

        result = prepare_repost_data(new_job, matched_job)

        assert result["repost_count"] == 3

    def test_repost_count_is_one_when_first_repost(self) -> None:
        """First repost of a job has repost_count = 1."""
        new_job = {
            "job_title": "Software Engineer",
            "company_name": "Acme Corp",
            "description": "Job description...",
        }
        matched_job = {
            "id": "matched-job-id",
            "repost_count": 0,
            "previous_posting_ids": None,
        }

        result = prepare_repost_data(new_job, matched_job)

        assert result["repost_count"] == 1

    def test_repost_count_defaults_to_one_when_matched_count_is_none(self) -> None:
        """repost_count defaults to 1 when matched job has None repost_count."""
        new_job = {
            "job_title": "Software Engineer",
            "company_name": "Acme Corp",
            "description": "Job description...",
        }
        matched_job = {
            "id": "matched-job-id",
            "repost_count": None,
            "previous_posting_ids": None,
        }

        result = prepare_repost_data(new_job, matched_job)

        assert result["repost_count"] == 1

    def test_new_job_fields_preserved_when_repost_prepared(self) -> None:
        """New job data fields are preserved in result."""
        new_job = {
            "job_title": "Software Engineer",
            "company_name": "Acme Corp",
            "description": "New job description...",
            "source_id": "source-123",
            "external_id": "ext-456",
            "salary_min": 100000,
        }
        matched_job = {
            "id": "matched-job-id",
            "repost_count": 0,
            "previous_posting_ids": None,
        }

        result = prepare_repost_data(new_job, matched_job)

        assert result["job_title"] == "Software Engineer"
        assert result["company_name"] == "Acme Corp"
        assert result["description"] == "New job description..."
        assert result["source_id"] == "source-123"
        assert result["external_id"] == "ext-456"
        assert result["salary_min"] == 100000

    def test_previous_posting_ids_correct_when_matched_has_empty_list(self) -> None:
        """Handles matched job with empty list for previous_posting_ids."""
        new_job = {
            "job_title": "Software Engineer",
            "company_name": "Acme Corp",
            "description": "Job description...",
        }
        matched_job = {
            "id": "matched-job-id",
            "repost_count": 0,
            "previous_posting_ids": [],
        }

        result = prepare_repost_data(new_job, matched_job)

        assert result["previous_posting_ids"] == ["matched-job-id"]
        assert result["repost_count"] == 1

    def test_input_dict_not_mutated_when_repost_prepared(self) -> None:
        """prepare_repost_data does not mutate the input new_job dict."""
        new_job = {
            "job_title": "Software Engineer",
            "company_name": "Acme Corp",
            "description": "Job description...",
        }
        matched_job = {
            "id": "matched-job-id",
            "repost_count": 0,
            "previous_posting_ids": None,
        }
        original_keys = set(new_job.keys())

        prepare_repost_data(new_job, matched_job)

        # Original dict should not have new keys
        assert set(new_job.keys()) == original_keys
        assert "status" not in new_job
        assert "previous_posting_ids" not in new_job
        assert "repost_count" not in new_job


# =============================================================================
# Repost Agent Context Tests (REQ-003 §8.3)
# =============================================================================


class TestGenerateRepostContextMessage:
    """Tests for generate_repost_context_message() function.

    REQ-003 §8.3: When a repost is detected and user previously applied,
    the agent communicates application history and offers to evaluate fresh.
    """

    def test_returns_none_when_no_prior_applications(self) -> None:
        """Returns None if user has no prior applications to previous postings."""
        result = generate_repost_context_message([])

        assert result is None

    def test_includes_applied_date_when_prior_application_exists(self) -> None:
        """Message includes the date user applied."""
        prior = PriorApplicationContext(
            job_posting_id="job-123",
            applied_at=datetime(2025, 1, 15, 10, 30, tzinfo=UTC),
            status="Rejected",
            status_updated_at=datetime(2025, 1, 20, 14, 0, tzinfo=UTC),
        )

        result = generate_repost_context_message([prior])

        assert result is not None
        assert "January 15, 2025" in result

    def test_includes_outcome_when_rejected(self) -> None:
        """Message includes 'rejected' outcome."""
        prior = PriorApplicationContext(
            job_posting_id="job-123",
            applied_at=datetime(2025, 1, 15, tzinfo=UTC),
            status="Rejected",
            status_updated_at=datetime(2025, 1, 20, tzinfo=UTC),
        )

        result = generate_repost_context_message([prior])

        assert result is not None
        assert "rejected" in result.lower()

    def test_includes_outcome_date_when_rejected(self) -> None:
        """Message includes the date of the outcome."""
        prior = PriorApplicationContext(
            job_posting_id="job-123",
            applied_at=datetime(2025, 1, 15, tzinfo=UTC),
            status="Rejected",
            status_updated_at=datetime(2025, 1, 20, tzinfo=UTC),
        )

        result = generate_repost_context_message([prior])

        assert result is not None
        assert "January 20, 2025" in result

    def test_offers_fresh_evaluation_when_repost_detected(self) -> None:
        """Message offers to evaluate the repost fresh."""
        prior = PriorApplicationContext(
            job_posting_id="job-123",
            applied_at=datetime(2025, 1, 15, tzinfo=UTC),
            status="Rejected",
            status_updated_at=datetime(2025, 1, 20, tzinfo=UTC),
        )

        result = generate_repost_context_message([prior])

        assert result is not None
        assert "evaluate" in result.lower() or "fresh" in result.lower()

    def test_indicates_repost_when_generating_message(self) -> None:
        """Message indicates the job is a repost."""
        prior = PriorApplicationContext(
            job_posting_id="job-123",
            applied_at=datetime(2025, 1, 15, tzinfo=UTC),
            status="Rejected",
            status_updated_at=datetime(2025, 1, 20, tzinfo=UTC),
        )

        result = generate_repost_context_message([prior])

        assert result is not None
        assert "repost" in result.lower() or "posted before" in result.lower()

    def test_handles_withdrawn_status_when_user_withdrew(self) -> None:
        """Message handles Withdrawn status correctly."""
        prior = PriorApplicationContext(
            job_posting_id="job-123",
            applied_at=datetime(2025, 1, 15, tzinfo=UTC),
            status="Withdrawn",
            status_updated_at=datetime(2025, 1, 18, tzinfo=UTC),
        )

        result = generate_repost_context_message([prior])

        assert result is not None
        assert "withdrew" in result.lower() or "withdrawn" in result.lower()

    def test_handles_offer_status_when_user_received_offer(self) -> None:
        """Message handles Offer status correctly."""
        prior = PriorApplicationContext(
            job_posting_id="job-123",
            applied_at=datetime(2025, 1, 15, tzinfo=UTC),
            status="Offer",
            status_updated_at=datetime(2025, 2, 1, tzinfo=UTC),
        )

        result = generate_repost_context_message([prior])

        assert result is not None
        assert "offer" in result.lower()

    def test_handles_accepted_status_when_user_accepted_offer(self) -> None:
        """Message handles Accepted status correctly."""
        prior = PriorApplicationContext(
            job_posting_id="job-123",
            applied_at=datetime(2025, 1, 15, tzinfo=UTC),
            status="Accepted",
            status_updated_at=datetime(2025, 2, 15, tzinfo=UTC),
        )

        result = generate_repost_context_message([prior])

        assert result is not None
        assert "accepted" in result.lower()

    def test_handles_still_pending_when_status_is_applied(self) -> None:
        """Message handles Applied status (still pending)."""
        prior = PriorApplicationContext(
            job_posting_id="job-123",
            applied_at=datetime(2025, 1, 15, tzinfo=UTC),
            status="Applied",
            status_updated_at=datetime(2025, 1, 15, tzinfo=UTC),
        )

        result = generate_repost_context_message([prior])

        assert result is not None
        # Should indicate application is still active/pending
        assert "pending" in result.lower() or "still" in result.lower()

    def test_handles_interviewing_status_when_in_progress(self) -> None:
        """Message handles Interviewing status (in progress)."""
        prior = PriorApplicationContext(
            job_posting_id="job-123",
            applied_at=datetime(2025, 1, 15, tzinfo=UTC),
            status="Interviewing",
            status_updated_at=datetime(2025, 1, 25, tzinfo=UTC),
        )

        result = generate_repost_context_message([prior])

        assert result is not None
        # Should indicate interviewing is in progress
        assert "interview" in result.lower()

    def test_uses_most_recent_when_multiple_prior_applications(self) -> None:
        """Uses most recent application when user applied to multiple versions."""
        older = PriorApplicationContext(
            job_posting_id="job-111",
            applied_at=datetime(2024, 6, 1, tzinfo=UTC),
            status="Rejected",
            status_updated_at=datetime(2024, 6, 15, tzinfo=UTC),
        )
        newer = PriorApplicationContext(
            job_posting_id="job-222",
            applied_at=datetime(2025, 1, 15, tzinfo=UTC),
            status="Withdrawn",
            status_updated_at=datetime(2025, 1, 20, tzinfo=UTC),
        )

        result = generate_repost_context_message([older, newer])

        assert result is not None
        # Should mention the most recent application (January 2025)
        assert "January 15, 2025" in result


# =============================================================================
# Same Source Update Tests (REQ-003 §9.1)
# =============================================================================


class TestPrepareSameSourceUpdate:
    """Tests for prepare_same_source_update() function.

    REQ-003 §9.1: When same external_id + source_id is encountered:
    - Update existing record (refresh data from source)
    - Preserve user-modified fields (status, is_favorite, dismissed_at)
    """

    def test_updates_source_provided_fields_when_new_data_available(self) -> None:
        """Source-provided fields are updated with new values."""
        existing = {
            "id": "job-123",
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "salary_min": None,
            "salary_max": None,
            "description": "Old description",
        }
        new_job = {
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "salary_min": 100000,
            "salary_max": 150000,
            "description": "Updated description with more details",
        }

        result = prepare_same_source_update(existing, new_job)

        assert result["salary_min"] == 100000
        assert result["salary_max"] == 150000
        assert result["description"] == "Updated description with more details"

    def test_preserves_user_modified_status_when_not_discovered(self) -> None:
        """User-modified status (not Discovered) is preserved."""
        existing = {
            "id": "job-123",
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "status": "Dismissed",
            "description": "Old description",
        }
        new_job = {
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "description": "Updated description",
        }

        result = prepare_same_source_update(existing, new_job)

        # Status should be preserved (user dismissed the job)
        assert result["status"] == "Dismissed"

    def test_preserves_is_favorite_when_user_favorited(self) -> None:
        """is_favorite flag is preserved when user has favorited."""
        existing = {
            "id": "job-123",
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "is_favorite": True,
            "description": "Old description",
        }
        new_job = {
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "description": "Updated description",
        }

        result = prepare_same_source_update(existing, new_job)

        assert result["is_favorite"] is True

    def test_preserves_dismissed_at_when_user_dismissed(self) -> None:
        """dismissed_at timestamp is preserved when user dismissed."""
        dismissed_time = datetime(2025, 1, 15, 10, 0, tzinfo=UTC)
        existing = {
            "id": "job-123",
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "dismissed_at": dismissed_time,
            "description": "Old description",
        }
        new_job = {
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "description": "Updated description",
        }

        result = prepare_same_source_update(existing, new_job)

        assert result["dismissed_at"] == dismissed_time

    def test_includes_last_verified_at_when_update_prepared(self) -> None:
        """last_verified_at is set to current time when update prepared."""
        existing = {
            "id": "job-123",
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "last_verified_at": None,
            "description": "Old description",
        }
        new_job = {
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "description": "Updated description",
        }

        result = prepare_same_source_update(existing, new_job)

        assert result["last_verified_at"] is not None
        assert isinstance(result["last_verified_at"], datetime)
        assert result["last_verified_at"].tzinfo is not None

    def test_preserves_id_when_update_prepared(self) -> None:
        """Existing job ID is preserved in update."""
        existing = {
            "id": "job-123",
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "description": "Old description",
        }
        new_job = {
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "description": "Updated description",
        }

        result = prepare_same_source_update(existing, new_job)

        assert result["id"] == "job-123"

    def test_preserves_first_seen_date_when_update_prepared(self) -> None:
        """first_seen_date is preserved (historical data)."""
        from datetime import date

        existing = {
            "id": "job-123",
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "first_seen_date": date(2025, 1, 1),
            "description": "Old description",
        }
        new_job = {
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "first_seen_date": date(2025, 1, 20),  # Newer date from re-scrape
            "description": "Updated description",
        }

        result = prepare_same_source_update(existing, new_job)

        # First seen date should be the original
        assert result["first_seen_date"] == date(2025, 1, 1)

    def test_updates_posted_date_when_source_has_newer_data(self) -> None:
        """posted_date is updated if source provides different value."""
        from datetime import date

        existing = {
            "id": "job-123",
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "posted_date": date(2025, 1, 1),
            "description": "Old description",
        }
        new_job = {
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "posted_date": date(2025, 1, 15),
            "description": "Updated description",
        }

        result = prepare_same_source_update(existing, new_job)

        # Posted date from source should be taken (it may be corrected)
        assert result["posted_date"] == date(2025, 1, 15)

    def test_preserves_scoring_fields_when_user_has_scores(self) -> None:
        """User-computed scores (fit_score, stretch_score) are preserved."""
        existing = {
            "id": "job-123",
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "fit_score": 85,
            "stretch_score": 20,
            "description": "Old description",
        }
        new_job = {
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "description": "Updated description",
        }

        result = prepare_same_source_update(existing, new_job)

        # Scores should be preserved (computed by agent, not source)
        assert result["fit_score"] == 85
        assert result["stretch_score"] == 20

    def test_preserves_ghost_score_when_existing_has_score(self) -> None:
        """ghost_score (computed by agent) is preserved."""
        existing = {
            "id": "job-123",
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "ghost_score": 45,
            "ghost_signals": {"days_open": 30, "repost_count": 1},
            "description": "Old description",
        }
        new_job = {
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "description": "Updated description",
        }

        result = prepare_same_source_update(existing, new_job)

        assert result["ghost_score"] == 45
        assert result["ghost_signals"] == {"days_open": 30, "repost_count": 1}

    def test_preserves_expired_at_when_existing_is_expired(self) -> None:
        """expired_at timestamp is preserved for expired jobs."""
        expired_time = datetime(2025, 1, 10, 12, 0, tzinfo=UTC)
        existing = {
            "id": "job-123",
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "expired_at": expired_time,
            "status": "Expired",
            "description": "Old description",
        }
        new_job = {
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "description": "Updated description",
        }

        result = prepare_same_source_update(existing, new_job)

        assert result["expired_at"] == expired_time
        assert result["status"] == "Expired"

    def test_preserves_persona_id_when_existing_has_persona(self) -> None:
        """persona_id is preserved (job belongs to specific persona)."""
        existing = {
            "id": "job-123",
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "persona_id": "persona-999",
            "description": "Old description",
        }
        new_job = {
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "persona_id": "different-persona",  # Source wouldn't change this
            "description": "Updated description",
        }

        result = prepare_same_source_update(existing, new_job)

        # Persona ID should be preserved (not changed)
        assert result["persona_id"] == "persona-999"

    def test_does_not_mutate_input_dicts_when_update_prepared(self) -> None:
        """Input dicts are not mutated by prepare_same_source_update."""
        existing = {
            "id": "job-123",
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "description": "Old description",
        }
        new_job = {
            "source_id": "source-1",
            "external_id": "ext-456",
            "job_title": "Software Engineer",
            "description": "Updated description",
        }
        existing_keys = set(existing.keys())
        new_keys = set(new_job.keys())

        prepare_same_source_update(existing, new_job)

        assert set(existing.keys()) == existing_keys
        assert set(new_job.keys()) == new_keys


# =============================================================================
# Cross Source Update Tests (REQ-003 §9.2)
# =============================================================================


class TestPrepareCrossSourceUpdate:
    """Tests for prepare_cross_source_update() function.

    REQ-003 §9.2: When same job found on different source:
    - Add new source to also_found_on JSONB
    - Merge data using priority rules (REQ-003 §9.3)
    - Preserve existing record (don't create duplicate)
    """

    def test_adds_source_to_empty_also_found_on(self) -> None:
        """First cross-source find adds source to empty also_found_on."""
        from app.services.job_deduplication import prepare_cross_source_update

        existing = {
            "id": "job-123",
            "source_id": "source-adzuna",
            "external_id": "adzuna-456",
            "job_title": "Scrum Master",
            "company_name": "Acme Corp",
            "also_found_on": {"sources": []},
            "description": "Original description",
        }
        new_source_info = {
            "source_id": "source-linkedin",
            "source_name": "LinkedIn",
            "external_id": "linkedin-789",
            "source_url": "https://linkedin.com/jobs/view/789",
        }

        result = prepare_cross_source_update(existing, new_source_info)

        assert len(result["also_found_on"]["sources"]) == 1
        assert result["also_found_on"]["sources"][0]["source_id"] == "source-linkedin"
        assert result["also_found_on"]["sources"][0]["external_id"] == "linkedin-789"
        assert result["also_found_on"]["sources"][0]["source_url"] == (
            "https://linkedin.com/jobs/view/789"
        )

    def test_adds_source_to_existing_also_found_on(self) -> None:
        """Second cross-source find appends to existing also_found_on."""
        from app.services.job_deduplication import prepare_cross_source_update

        existing = {
            "id": "job-123",
            "source_id": "source-adzuna",
            "external_id": "adzuna-456",
            "job_title": "Scrum Master",
            "company_name": "Acme Corp",
            "also_found_on": {
                "sources": [
                    {
                        "source_id": "source-linkedin",
                        "external_id": "linkedin-789",
                        "source_url": "https://linkedin.com/jobs/view/789",
                        "found_at": "2025-01-20T10:00:00Z",
                    }
                ]
            },
            "description": "Original description",
        }
        new_source_info = {
            "source_id": "source-indeed",
            "source_name": "Indeed",
            "external_id": "indeed-111",
            "source_url": "https://indeed.com/jobs?id=111",
        }

        result = prepare_cross_source_update(existing, new_source_info)

        # Should have 2 sources now
        assert len(result["also_found_on"]["sources"]) == 2
        # Original source preserved
        assert result["also_found_on"]["sources"][0]["source_id"] == "source-linkedin"
        # New source added
        assert result["also_found_on"]["sources"][1]["source_id"] == "source-indeed"
        assert result["also_found_on"]["sources"][1]["external_id"] == "indeed-111"

    def test_includes_found_at_timestamp(self) -> None:
        """New source entry includes found_at timestamp."""
        from app.services.job_deduplication import prepare_cross_source_update

        existing = {
            "id": "job-123",
            "source_id": "source-adzuna",
            "external_id": "adzuna-456",
            "job_title": "Scrum Master",
            "company_name": "Acme Corp",
            "also_found_on": {"sources": []},
            "description": "Original description",
        }
        new_source_info = {
            "source_id": "source-linkedin",
            "source_name": "LinkedIn",
            "external_id": "linkedin-789",
            "source_url": "https://linkedin.com/jobs/view/789",
        }

        result = prepare_cross_source_update(existing, new_source_info)

        assert "found_at" in result["also_found_on"]["sources"][0]
        # Should be ISO format timestamp
        found_at = result["also_found_on"]["sources"][0]["found_at"]
        assert isinstance(found_at, str)
        assert "T" in found_at  # ISO format

    def test_merges_salary_when_new_source_has_it(self) -> None:
        """Salary data is merged when new source has it and existing doesn't."""
        from app.services.job_deduplication import prepare_cross_source_update

        existing = {
            "id": "job-123",
            "source_id": "source-adzuna",
            "external_id": "adzuna-456",
            "job_title": "Scrum Master",
            "company_name": "Acme Corp",
            "also_found_on": {"sources": []},
            "salary_min": None,
            "salary_max": None,
            "description": "Original description",
        }
        new_source_info = {
            "source_id": "source-linkedin",
            "source_name": "LinkedIn",
            "external_id": "linkedin-789",
            "source_url": "https://linkedin.com/jobs/view/789",
            "salary_min": 120000,
            "salary_max": 150000,
        }

        result = prepare_cross_source_update(existing, new_source_info)

        assert result["salary_min"] == 120000
        assert result["salary_max"] == 150000

    def test_prefers_ats_url_over_aggregator_url(self) -> None:
        """ATS apply_url is preferred over aggregator URL per REQ-003 §9.3."""
        from app.services.job_deduplication import prepare_cross_source_update

        existing = {
            "id": "job-123",
            "source_id": "source-adzuna",
            "external_id": "adzuna-456",
            "job_title": "Scrum Master",
            "company_name": "Acme Corp",
            "also_found_on": {"sources": []},
            "apply_url": "https://adzuna.com/redirect/12345",
            "description": "Original description",
        }
        new_source_info = {
            "source_id": "source-linkedin",
            "source_name": "LinkedIn",
            "external_id": "linkedin-789",
            "source_url": "https://linkedin.com/jobs/view/789",
            "apply_url": "https://acme.greenhouse.io/apply/scrum-master",
        }

        result = prepare_cross_source_update(existing, new_source_info)

        # ATS URL should win over aggregator
        assert result["apply_url"] == "https://acme.greenhouse.io/apply/scrum-master"

    def test_preserves_existing_id(self) -> None:
        """Existing job ID is preserved (no new record created)."""
        from app.services.job_deduplication import prepare_cross_source_update

        existing = {
            "id": "job-123",
            "source_id": "source-adzuna",
            "external_id": "adzuna-456",
            "job_title": "Scrum Master",
            "company_name": "Acme Corp",
            "also_found_on": {"sources": []},
            "description": "Original description",
        }
        new_source_info = {
            "source_id": "source-linkedin",
            "source_name": "LinkedIn",
            "external_id": "linkedin-789",
            "source_url": "https://linkedin.com/jobs/view/789",
        }

        result = prepare_cross_source_update(existing, new_source_info)

        assert result["id"] == "job-123"

    def test_does_not_duplicate_same_source(self) -> None:
        """Same source is not added twice to also_found_on."""
        from app.services.job_deduplication import prepare_cross_source_update

        existing = {
            "id": "job-123",
            "source_id": "source-adzuna",
            "external_id": "adzuna-456",
            "job_title": "Scrum Master",
            "company_name": "Acme Corp",
            "also_found_on": {
                "sources": [
                    {
                        "source_id": "source-linkedin",
                        "external_id": "linkedin-789",
                        "source_url": "https://linkedin.com/jobs/view/789",
                        "found_at": "2025-01-20T10:00:00Z",
                    }
                ]
            },
            "description": "Original description",
        }
        # Same source_id as already in also_found_on
        new_source_info = {
            "source_id": "source-linkedin",
            "source_name": "LinkedIn",
            "external_id": "linkedin-789",
            "source_url": "https://linkedin.com/jobs/view/789",
        }

        result = prepare_cross_source_update(existing, new_source_info)

        # Should still be only 1 source (not duplicated)
        assert len(result["also_found_on"]["sources"]) == 1

    def test_does_not_mutate_input_dicts(self) -> None:
        """Input dicts are not mutated by prepare_cross_source_update."""
        from app.services.job_deduplication import prepare_cross_source_update

        existing = {
            "id": "job-123",
            "source_id": "source-adzuna",
            "external_id": "adzuna-456",
            "job_title": "Scrum Master",
            "company_name": "Acme Corp",
            "also_found_on": {"sources": []},
            "description": "Original description",
        }
        new_source_info = {
            "source_id": "source-linkedin",
            "source_name": "LinkedIn",
            "external_id": "linkedin-789",
            "source_url": "https://linkedin.com/jobs/view/789",
        }
        original_also_found_on = existing["also_found_on"]["sources"].copy()

        prepare_cross_source_update(existing, new_source_info)

        # Original dict unchanged
        assert existing["also_found_on"]["sources"] == original_also_found_on

    def test_prefers_earlier_posted_date(self) -> None:
        """Earlier posted_date is preferred per REQ-003 §9.3."""
        from app.services.job_deduplication import prepare_cross_source_update

        existing = {
            "id": "job-123",
            "source_id": "source-adzuna",
            "external_id": "adzuna-456",
            "job_title": "Scrum Master",
            "company_name": "Acme Corp",
            "also_found_on": {"sources": []},
            "posted_date": "2025-01-20",
            "description": "Original description",
        }
        new_source_info = {
            "source_id": "source-linkedin",
            "source_name": "LinkedIn",
            "external_id": "linkedin-789",
            "source_url": "https://linkedin.com/jobs/view/789",
            "posted_date": "2025-01-15",  # Earlier date
        }

        result = prepare_cross_source_update(existing, new_source_info)

        assert result["posted_date"] == "2025-01-15"

    def test_prefers_longer_description(self) -> None:
        """Longer description is preferred per REQ-003 §9.3."""
        from app.services.job_deduplication import prepare_cross_source_update

        existing = {
            "id": "job-123",
            "source_id": "source-adzuna",
            "external_id": "adzuna-456",
            "job_title": "Scrum Master",
            "company_name": "Acme Corp",
            "also_found_on": {"sources": []},
            "description": "Short description",
        }
        new_source_info = {
            "source_id": "source-linkedin",
            "source_name": "LinkedIn",
            "external_id": "linkedin-789",
            "source_url": "https://linkedin.com/jobs/view/789",
            "description": "Much longer and more detailed description with requirements",
        }

        result = prepare_cross_source_update(existing, new_source_info)

        assert result["description"] == (
            "Much longer and more detailed description with requirements"
        )


# =============================================================================
# Cross Source Message Tests (REQ-003 §9.2)
# =============================================================================


class TestGenerateCrossSourceMessage:
    """Tests for generate_cross_source_message() function.

    REQ-003 §9.2: Agent communication for cross-source finds.
    Example: "This Scrum Master role at Acme Corp was also found on LinkedIn and Indeed."
    """

    def test_generates_message_with_one_other_source(self) -> None:
        """Message for job found on one other source."""
        from app.services.job_deduplication import generate_cross_source_message

        also_found_on = {
            "sources": [
                {
                    "source_id": "source-linkedin",
                    "source_name": "LinkedIn",
                    "external_id": "linkedin-789",
                    "source_url": "https://linkedin.com/jobs/view/789",
                    "found_at": "2025-01-20T10:00:00Z",
                }
            ]
        }

        result = generate_cross_source_message(
            job_title="Scrum Master",
            company_name="Acme Corp",
            also_found_on=also_found_on,
        )

        assert result is not None
        assert "Scrum Master" in result
        assert "Acme Corp" in result
        assert "LinkedIn" in result

    def test_generates_message_with_multiple_sources(self) -> None:
        """Message for job found on multiple other sources."""
        from app.services.job_deduplication import generate_cross_source_message

        also_found_on = {
            "sources": [
                {
                    "source_id": "source-linkedin",
                    "source_name": "LinkedIn",
                    "external_id": "linkedin-789",
                    "source_url": "https://linkedin.com/jobs/view/789",
                    "found_at": "2025-01-20T10:00:00Z",
                },
                {
                    "source_id": "source-indeed",
                    "source_name": "Indeed",
                    "external_id": "indeed-111",
                    "source_url": "https://indeed.com/jobs?id=111",
                    "found_at": "2025-01-21T14:00:00Z",
                },
            ]
        }

        result = generate_cross_source_message(
            job_title="Scrum Master",
            company_name="Acme Corp",
            also_found_on=also_found_on,
        )

        assert result is not None
        assert "LinkedIn" in result
        assert "Indeed" in result
        # Should use "and" for natural language
        assert " and " in result or ", " in result

    def test_returns_none_for_empty_sources(self) -> None:
        """Returns None when no other sources."""
        from app.services.job_deduplication import generate_cross_source_message

        also_found_on: dict = {"sources": []}

        result = generate_cross_source_message(
            job_title="Scrum Master",
            company_name="Acme Corp",
            also_found_on=also_found_on,
        )

        assert result is None

    def test_returns_none_for_missing_sources_key(self) -> None:
        """Returns None when sources key is missing."""
        from app.services.job_deduplication import generate_cross_source_message

        also_found_on: dict = {}

        result = generate_cross_source_message(
            job_title="Scrum Master",
            company_name="Acme Corp",
            also_found_on=also_found_on,
        )

        assert result is None

    def test_uses_source_name_when_available(self) -> None:
        """Uses source_name for display if available."""
        from app.services.job_deduplication import generate_cross_source_message

        also_found_on = {
            "sources": [
                {
                    "source_id": "source-123",
                    "source_name": "RemoteOK",
                    "external_id": "remote-456",
                    "source_url": "https://remoteok.com/jobs/456",
                    "found_at": "2025-01-20T10:00:00Z",
                }
            ]
        }

        result = generate_cross_source_message(
            job_title="DevOps Engineer",
            company_name="TechCo",
            also_found_on=also_found_on,
        )

        assert result is not None
        assert "RemoteOK" in result
