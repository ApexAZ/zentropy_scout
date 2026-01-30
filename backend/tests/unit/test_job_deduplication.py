"""Tests for job deduplication service.

REQ-007 §6.6 + REQ-003 §9: Deduplication Logic tests.

Tests verify:
- is_duplicate() return values: update_existing, add_to_also_found_on,
  create_linked_repost, create_new
- is_similar_title() per REQ-003 §8.1 (Levenshtein, contains, word overlap)
- description_similarity() for >85% threshold
- also_found_on JSONB structure per REQ-003 §9.2
- Priority rules for merging data per REQ-003 §9.3
"""

from app.services.job_deduplication import (
    DuplicateResult,
    calculate_description_similarity,
    is_duplicate,
    is_similar_title,
    merge_job_data,
    prepare_repost_data,
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
# DuplicateResult Structure Tests
# =============================================================================


class TestDuplicateResult:
    """Tests for DuplicateResult dataclass.

    REQ-007 §6.6: Result structure for deduplication decisions.
    """

    def test_create_new_result_has_no_matched_id(self) -> None:
        """create_new action has matched_job_id as None."""
        result = DuplicateResult(action="create_new", matched_job_id=None)

        assert result.action == "create_new"
        assert result.matched_job_id is None

    def test_update_existing_result_has_matched_id(self) -> None:
        """update_existing action has matched_job_id."""
        result = DuplicateResult(action="update_existing", matched_job_id="job-123")

        assert result.action == "update_existing"
        assert result.matched_job_id == "job-123"


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
