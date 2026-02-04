# Scoring Algorithm Validation Guide

**REQ-008 §11.2: Validation Approach**

This document describes how to validate the Zentropy Scout scoring algorithm against human-labeled golden set data.

---

## Overview

The scoring validation system ensures that algorithm-generated Fit and Stretch scores correlate with human judgment. Per REQ-008 §11.2, validation requires:

1. **Golden Set**: 50 curated Persona/Job pairs with human-labeled scores
2. **Correlation Check**: Pearson correlation coefficient r > 0.8 for both Fit and Stretch
3. **A/B Testing**: Runtime tracking of user behavior vs. scores (future)

---

## Golden Set

### Location

```
backend/tests/fixtures/golden_set.json
```

### Structure

```json
{
  "metadata": {
    "version": "0.1.0",
    "created_date": "2026-02-04",
    "description": "...",
    "curated_by": "Brian",
    "target_correlation": 0.8
  },
  "entries": [
    {
      "id": "gs-001",
      "persona_summary": "Brief description of persona...",
      "job_summary": "Brief description of job...",
      "human_fit_score": 85,
      "human_stretch_score": 45,
      "notes": "Optional rationale for scores"
    }
  ]
}
```

### Current Status

- **Target**: 50 entries
- **Current**: 5 seed entries (diverse scoring scenarios)
- **Version**: 0.1.0

### Adding New Entries

When adding entries to the golden set:

1. **Diverse scenarios**: Include various match types:
   - High fit / low stretch (perfect match, limited growth)
   - Low fit / high stretch (career changer, growth opportunity)
   - Moderate fit / moderate stretch (typical applicant)
   - Edge cases (underqualified, overqualified, career mismatch)

2. **Score rationale**: Include `notes` explaining why scores were assigned

3. **Unique IDs**: Use format `gs-XXX` where XXX is sequential

4. **Validation**: Run fixture tests after changes:
   ```bash
   cd backend
   .venv/bin/pytest tests/unit/test_golden_set_fixture.py -v
   ```

---

## Running Validation

### Prerequisites

1. Golden set must have at least 5 entries (minimum for meaningful correlation)
2. Algorithm must be able to generate scores for all entries

### Validation Code

```python
from pathlib import Path
from app.services.golden_set import load_golden_set
from app.services.score_correlation import validate_scores_against_golden_set

# Load golden set
golden_set = load_golden_set(Path("tests/fixtures/golden_set.json"))

# Generate algorithm scores for each entry
# (This would use the actual scoring engine)
algorithm_scores = {}
for entry in golden_set.entries:
    # TODO: Replace with actual scoring call
    algorithm_scores[entry.id] = {
        "fit": calculate_fit_score(entry.persona_summary, entry.job_summary),
        "stretch": calculate_stretch_score(entry.persona_summary, entry.job_summary),
    }

# Run validation
result = validate_scores_against_golden_set(golden_set, algorithm_scores)

# Check results
print(f"Fit Correlation:     r = {result.correlation.fit_correlation:.3f}")
print(f"Stretch Correlation: r = {result.correlation.stretch_correlation:.3f}")
print(f"Target Threshold:    r > {result.target_threshold}")
print(f"Validation Passed:   {result.passed}")
```

### Interpreting Results

| Correlation | Interpretation |
|-------------|----------------|
| r > 0.9     | Excellent - algorithm closely matches human judgment |
| r > 0.8     | Good - meets validation threshold |
| r > 0.6     | Moderate - needs investigation |
| r < 0.6     | Poor - algorithm may have systemic issues |

### Debugging Low Correlation

If validation fails, examine `entry_results`:

```python
for entry in result.entry_results:
    if abs(entry["fit_error"]) > 20:  # Large discrepancy
        print(f"{entry['id']}: Fit error = {entry['fit_error']}")
        print(f"  Human: {entry['human_fit']}, Algorithm: {entry['algo_fit']}")
```

Common issues:
- **Systematic bias**: Algorithm consistently over/under-scores
- **Category confusion**: Algorithm struggles with specific persona types
- **Missing signals**: Algorithm ignoring important factors

---

## Correlation Calculation

The validation uses Pearson correlation coefficient:

```
r = Σ[(xi - x̄)(yi - ȳ)] / √[Σ(xi - x̄)² × Σ(yi - ȳ)²]
```

Where:
- `xi` = human-labeled scores
- `yi` = algorithm-generated scores
- `x̄`, `ȳ` = means

Properties:
- Range: -1.0 to +1.0
- +1.0 = perfect positive correlation
- 0 = no correlation
- -1.0 = perfect negative correlation (inverted scores)

---

## A/B Testing (Future)

REQ-008 §11.2 specifies A/B testing as part of validation:

> Track user behavior (apply rate, dismiss rate) vs. scores

This will be implemented after the core application is functional. Metrics to track:

| Metric | Calculation |
|--------|-------------|
| Apply Rate by Score Bucket | % of jobs applied to, grouped by score range |
| Dismiss Rate by Score Bucket | % of jobs dismissed, grouped by score range |
| Precision | High-scored jobs that users actually applied to |
| Recall | Applied jobs that had high algorithm scores |

Expected behavior:
- Users should apply to high-scoring jobs more often
- Users should dismiss low-scoring jobs more often

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0   | 2026-02-04 | Initial seed entries (5) |

---

## References

- REQ-008 §11.2: Validation Approach
- `backend/app/services/golden_set.py`: Schema and loader
- `backend/app/services/score_correlation.py`: Correlation utilities
- `backend/tests/fixtures/golden_set.json`: Golden set data
