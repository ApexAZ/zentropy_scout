"""Tests for embedding cost estimation.

REQ-008 §10.3: Cost estimates for embedding operations.

NOTE: REQ-008 §10.3 provides rough cost estimates (100 jobs/day ~$3/month).
Back-calculating these estimates implies ~50,000 tokens per job, which is
unrealistically high for embeddings alone (~500 tokens typical). The REQ
estimates may include LLM costs or be order-of-magnitude guidance.

These tests verify the calculation logic is correct given actual token usage.
"""

import pytest

from app.services.embedding_cost import (
    EMBEDDING_MODELS,
    EmbeddingCostEstimate,
    estimate_embedding_cost,
    estimate_monthly_cost,
)

# =============================================================================
# Test: Cost Estimation
# =============================================================================


class TestEstimateEmbeddingCost:
    """Test single embedding cost estimation."""

    def test_zero_tokens_returns_zero_cost(self):
        """Zero tokens should cost $0."""
        result = estimate_embedding_cost(0)

        assert result.cost_usd == 0.0
        assert result.total_tokens == 0

    def test_1000_tokens_costs_0_00002(self):
        """1000 tokens at text-embedding-3-small costs $0.00002."""
        result = estimate_embedding_cost(1000)

        assert result.cost_usd == pytest.approx(0.00002)
        assert result.total_tokens == 1000
        assert result.model == "text-embedding-3-small"

    def test_100000_tokens_costs_0_002(self):
        """100,000 tokens should cost $0.002."""
        result = estimate_embedding_cost(100_000)

        assert result.cost_usd == pytest.approx(0.002)

    def test_custom_model_uses_different_pricing(self):
        """Custom model should use its pricing."""
        result = estimate_embedding_cost(1000, model="text-embedding-3-large")

        # text-embedding-3-large costs $0.00013 per 1K tokens
        assert result.cost_usd == pytest.approx(0.00013)
        assert result.model == "text-embedding-3-large"

    def test_unknown_model_raises_valueerror(self):
        """Unknown model should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown embedding model"):
            estimate_embedding_cost(1000, model="unknown-model")

    def test_negative_tokens_raises_valueerror(self):
        """Negative tokens should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            estimate_embedding_cost(-100)

    def test_returns_cost_estimate_dataclass(self):
        """Result should be an EmbeddingCostEstimate."""
        result = estimate_embedding_cost(5000)

        assert isinstance(result, EmbeddingCostEstimate)
        assert result.total_tokens == 5000
        assert result.price_per_1k_tokens == pytest.approx(0.00002)


# =============================================================================
# Test: Monthly Cost Projection
# =============================================================================


class TestEstimateMonthlyCost:
    """Test monthly cost projections based on volume."""

    def test_cost_scales_linearly_with_volume(self):
        """Cost should scale linearly with job volume."""
        result_100 = estimate_monthly_cost(jobs_per_day=100)
        result_500 = estimate_monthly_cost(jobs_per_day=500)
        result_2000 = estimate_monthly_cost(jobs_per_day=2000)

        # Cost should be proportional to volume
        ratio_500_to_100 = result_500.monthly_cost_usd / result_100.monthly_cost_usd
        ratio_2000_to_500 = result_2000.monthly_cost_usd / result_500.monthly_cost_usd

        assert ratio_500_to_100 == pytest.approx(5.0)  # 500/100 = 5
        assert ratio_2000_to_500 == pytest.approx(4.0)  # 2000/500 = 4

    def test_calculation_matches_formula(self):
        """Cost should match: tokens_per_job * jobs * days * price_per_token."""
        result = estimate_monthly_cost(jobs_per_day=100)

        # Manual calculation
        tokens_per_job = result.total_tokens_per_job
        expected = (tokens_per_job * 100 * 30 / 1000) * 0.00002

        assert result.monthly_cost_usd == pytest.approx(expected)

    def test_realistic_embedding_cost_is_low(self):
        """Embedding-only cost for 100 jobs/day should be < $1/month.

        NOTE: REQ-008 §10.3 shows ~$3/month for 100 jobs/day, which implies
        ~50,000 tokens/job. Actual embedding tokens are ~110/job (title +
        culture text). The REQ estimate likely includes LLM API costs.
        """
        result = estimate_monthly_cost(jobs_per_day=100)

        # With ~110 tokens/job, cost is ~$0.0066/month, not $3
        # This verifies embedding costs are minimal
        assert result.monthly_cost_usd < 1.0

    def test_zero_jobs_returns_zero_cost(self):
        """Zero jobs should cost $0."""
        result = estimate_monthly_cost(jobs_per_day=0)

        assert result.monthly_cost_usd == 0.0

    def test_negative_jobs_raises_valueerror(self):
        """Negative jobs should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            estimate_monthly_cost(jobs_per_day=-10)

    def test_includes_breakdown_by_category(self):
        """Result should include token breakdown by category."""
        result = estimate_monthly_cost(jobs_per_day=100)

        assert result.job_title_tokens_per_job > 0
        assert result.culture_tokens_per_job > 0
        assert result.total_tokens_per_job > 0
        assert result.days_per_month == 30

    def test_token_breakdown_sums_to_total(self):
        """Token breakdown should sum to total tokens per job."""
        result = estimate_monthly_cost(jobs_per_day=100)

        expected_total = result.job_title_tokens_per_job + result.culture_tokens_per_job
        assert result.total_tokens_per_job == expected_total


# =============================================================================
# Test: Model Constants
# =============================================================================


class TestEmbeddingModels:
    """Test embedding model constants."""

    def test_small_cheaper_than_large(self):
        """text-embedding-3-small should be cheaper than large."""
        small = EMBEDDING_MODELS["text-embedding-3-small"]
        large = EMBEDDING_MODELS["text-embedding-3-large"]

        assert small["price_per_1k_tokens"] < large["price_per_1k_tokens"]
