"""Embedding cost estimation utilities.

REQ-008 §10.3: Cost estimates for embedding operations.

This module provides cost estimation for OpenAI embedding API calls.
Pricing is based on text-embedding-3-small at $0.00002 per 1K tokens.

Cost Table (REQ-008 §10.3):
┌─────────────────┬──────────────────────────────┐
│     Volume      │ Estimated Monthly Cost (USD) │
├─────────────────┼──────────────────────────────┤
│ 100 jobs/day    │ ~$3                          │
│ 500 jobs/day    │ ~$15                         │
│ 2000 jobs/day   │ ~$60                         │
└─────────────────┴──────────────────────────────┘

These estimates assume:
- text-embedding-3-small model ($0.00002/1K tokens)
- Average job embedding: ~150 tokens (title + culture)
- 30 days per month
"""

from dataclasses import dataclass

# =============================================================================
# Constants
# =============================================================================

# Embedding model pricing (per 1K tokens) as of January 2025
# Source: https://openai.com/pricing
EMBEDDING_MODELS: dict[str, dict[str, float | int]] = {
    "text-embedding-3-small": {
        "price_per_1k_tokens": 0.00002,  # $0.02 per million tokens
        "dimensions": 1536,
    },
    "text-embedding-3-large": {
        "price_per_1k_tokens": 0.00013,  # $0.13 per million tokens
        "dimensions": 3072,
    },
    "text-embedding-ada-002": {
        "price_per_1k_tokens": 0.0001,  # Legacy model
        "dimensions": 1536,
    },
}

# Default model for cost estimates
DEFAULT_MODEL = "text-embedding-3-small"

# Estimated average tokens per job embedding
# Based on typical job posting text:
# - Job title: ~10 tokens
# - Culture text: ~100 tokens
# - Total per job: ~110 tokens (rounded up to account for variance)
_AVG_JOB_TITLE_TOKENS = 10
_AVG_CULTURE_TOKENS = 100
_AVG_TOKENS_PER_JOB = _AVG_JOB_TITLE_TOKENS + _AVG_CULTURE_TOKENS

# Days per month for cost projections
_DAYS_PER_MONTH = 30


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class EmbeddingCostEstimate:
    """Result of a single embedding cost calculation.

    Attributes:
        total_tokens: Number of tokens processed.
        cost_usd: Estimated cost in US dollars.
        model: Embedding model used for pricing.
        price_per_1k_tokens: Price per 1,000 tokens for the model.
    """

    total_tokens: int
    cost_usd: float
    model: str
    price_per_1k_tokens: float


@dataclass
class MonthlyCostEstimate:
    """Monthly cost projection for a given job volume.

    Attributes:
        jobs_per_day: Number of jobs processed per day.
        monthly_cost_usd: Estimated total monthly cost in US dollars.
        total_tokens_per_job: Estimated tokens per job embedding.
        job_title_tokens_per_job: Estimated tokens for job title.
        culture_tokens_per_job: Estimated tokens for culture text.
        days_per_month: Number of days used for calculation.
        model: Embedding model used for pricing.
    """

    jobs_per_day: int
    monthly_cost_usd: float
    total_tokens_per_job: int
    job_title_tokens_per_job: int
    culture_tokens_per_job: int
    days_per_month: int
    model: str


# =============================================================================
# Cost Estimation Functions
# =============================================================================


def estimate_embedding_cost(
    total_tokens: int,
    model: str = DEFAULT_MODEL,
) -> EmbeddingCostEstimate:
    """Estimate cost for an embedding operation.

    REQ-008 §10.3: Cost estimates for embedding operations.

    Args:
        total_tokens: Number of tokens to embed.
        model: Embedding model name (default: text-embedding-3-small).

    Returns:
        EmbeddingCostEstimate with cost breakdown.

    Raises:
        ValueError: If model is unknown or tokens is negative.

    Example:
        >>> result = estimate_embedding_cost(5000)
        >>> print(f"Cost: ${result.cost_usd:.6f}")
        Cost: $0.000100
    """
    if total_tokens < 0:
        msg = f"total_tokens cannot be negative, got {total_tokens}"
        raise ValueError(msg)

    if model not in EMBEDDING_MODELS:
        msg = f"Unknown embedding model: {model}. Known models: {list(EMBEDDING_MODELS.keys())}"
        raise ValueError(msg)

    model_info = EMBEDDING_MODELS[model]
    price_per_1k = model_info["price_per_1k_tokens"]

    # Cost = (tokens / 1000) * price_per_1k_tokens
    cost = (total_tokens / 1000) * float(price_per_1k)

    return EmbeddingCostEstimate(
        total_tokens=total_tokens,
        cost_usd=cost,
        model=model,
        price_per_1k_tokens=float(price_per_1k),
    )


def estimate_monthly_cost(
    jobs_per_day: int,
    model: str = DEFAULT_MODEL,
) -> MonthlyCostEstimate:
    """Estimate monthly embedding cost for a given job volume.

    REQ-008 §10.3: Cost table for volume-based planning.

    Uses conservative estimates for tokens per job:
    - Job title: ~10 tokens
    - Culture text: ~100 tokens
    - Total: ~110 tokens per job

    Args:
        jobs_per_day: Number of jobs to process per day.
        model: Embedding model name (default: text-embedding-3-small).

    Returns:
        MonthlyCostEstimate with detailed breakdown.

    Raises:
        ValueError: If jobs_per_day is negative or model is unknown.

    Example:
        >>> result = estimate_monthly_cost(100)
        >>> print(f"Monthly cost: ${result.monthly_cost_usd:.2f}")
        Monthly cost: $6.60
    """
    if jobs_per_day < 0:
        msg = f"jobs_per_day cannot be negative, got {jobs_per_day}"
        raise ValueError(msg)

    if model not in EMBEDDING_MODELS:
        msg = f"Unknown embedding model: {model}. Known models: {list(EMBEDDING_MODELS.keys())}"
        raise ValueError(msg)

    model_info = EMBEDDING_MODELS[model]
    price_per_1k = float(model_info["price_per_1k_tokens"])

    # Calculate monthly tokens
    tokens_per_day = jobs_per_day * _AVG_TOKENS_PER_JOB
    tokens_per_month = tokens_per_day * _DAYS_PER_MONTH

    # Calculate cost
    monthly_cost = (tokens_per_month / 1000) * price_per_1k

    return MonthlyCostEstimate(
        jobs_per_day=jobs_per_day,
        monthly_cost_usd=monthly_cost,
        total_tokens_per_job=_AVG_TOKENS_PER_JOB,
        job_title_tokens_per_job=_AVG_JOB_TITLE_TOKENS,
        culture_tokens_per_job=_AVG_CULTURE_TOKENS,
        days_per_month=_DAYS_PER_MONTH,
        model=model,
    )
