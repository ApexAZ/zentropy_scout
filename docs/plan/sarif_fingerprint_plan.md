# SARIF Fingerprint Normalization Plan

**Goal:** Make ZAP DAST alert dismissals persist across scans by adding stable `partialFingerprints` to the SARIF output.

**Root cause:** ZAP fuzzes endpoints with random numeric payloads (e.g., `api/v1/personas/8297929860933747743`). Each scan uses different numbers, so GitHub treats every scan's findings as brand-new alerts. Dismissed alerts don't carry over.

**Solution:** In `zap-to-sarif.py`, normalize dynamic path segments to `{id}` and compute a stable `primaryLocationLineHash` fingerprint for each result. GitHub uses this fingerprint for deduplication — same fingerprint = same alert.

---

## Research Summary

- **GitHub only reads `partialFingerprints.primaryLocationLineHash`** — all other keys are ignored
- **When present, GitHub uses the value as-is** — no auto-computation attempted
- **When absent (current state), upload-sarif tries to hash the source file** — fails silently for DAST URLs, so no fingerprint is generated, causing duplicates
- **The value is an opaque string** — any deterministic hash works (SHA-256, MD5, etc.)
- **Alert identity** = `tool.driver.name` + `ruleId` + `primaryLocationLineHash`
- **`artifactLocation.uri` must also be stable** — it determines display location and contributes to matching

Sources: [GitHub SARIF docs](https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning), [codeql-action fingerprints.ts](https://github.com/github/codeql-action/blob/main/src/fingerprints.ts), [OASIS SARIF 2.1.0 §3.27.17](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html)

---

## Changes

### File: `.github/scripts/zap-to-sarif.py`

#### 1. Add `_normalize_path_segment(segment)` function
- Replace UUID patterns (`[0-9a-f]{8}-...`) with `{id}`
- Replace large numeric ZAP payloads (10+ digits) with `{id}`
- Leave named segments (`resume_id`, `persona_job_id`, etc.) untouched
- Threshold of 10+ digits avoids false positives on short numbers (port numbers, pagination, etc.)

#### 2. Add `_normalize_path(path)` function
- Split path by `/`, normalize each segment, rejoin
- Example: `api/v1/personas/8297929860933747743` → `api/v1/personas/{id}`
- Example: `api/v1/job-variants/variant_id/3811768465121217484` → `api/v1/job-variants/variant_id/{id}`

#### 3. Add `_compute_fingerprint(rule_id, method, normalized_path)` function
- Input: `"{rule_id}|{method}|{normalized_path}"`
- Hash: SHA-256 hex digest (first 16 chars for readability)
- Append `:1` suffix (GitHub's convention for occurrence count)
- Return: e.g., `"a1b2c3d4e5f6g7h8:1"`

#### 4. Update `convert()` function
- Apply `_normalize_path()` to `artifactLocation.uri` (instead of raw `_uri_to_path()`)
- Add `partialFingerprints.primaryLocationLineHash` to each result

### File: `.github/scripts/test_zap_to_sarif.py`

#### Path normalization tests
- `test_normalizes_large_numbers_to_id` — `8297929860933747743` → `{id}`
- `test_normalizes_uuid_to_id` — `550e8400-e29b-41d4-a716-446655440000` → `{id}`
- `test_preserves_named_segments` — `resume_id`, `persona_job_id` unchanged
- `test_preserves_short_numbers` — `v1`, `v2` unchanged
- `test_preserves_api_prefix` — `api/v1/personas` unchanged when no dynamic segment
- `test_normalizes_multiple_dynamic_segments` — handles paths with 2+ dynamic segments

#### Fingerprint tests
- `test_fingerprint_present_in_results` — every result has `partialFingerprints.primaryLocationLineHash`
- `test_same_endpoint_same_fingerprint` — identical rule + method + path → identical hash
- `test_different_methods_different_fingerprint` — GET vs POST → different hash
- `test_different_rules_different_fingerprint` — rule 10038 vs 40018 → different hash
- `test_different_endpoints_different_fingerprint` — `/personas` vs `/jobs` → different hash
- `test_fingerprint_stable_across_zap_payloads` — two different random numbers for same endpoint → same hash (the core dedup test)

#### Integration test
- `test_normalized_uri_in_artifact_location` — verify the SARIF output uses `{id}` not raw numbers

### File: `.github/workflows/zap-dast.yml`

No changes needed — the converter already sits between ZAP output and SARIF upload.

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Normalization too aggressive (replaces real path segments) | 10+ digit threshold; UUID regex is precise; test with real ZAP output paths |
| Normalization too conservative (misses some payloads) | Review actual ZAP SARIF from recent scans; add patterns as needed |
| Fingerprint collision (different findings get same hash) | SHA-256 on rule + method + path; collision astronomically unlikely |
| Breaking existing SARIF tests | All 31 existing tests must still pass |
| SARIF schema violation | `partialFingerprints` is a standard SARIF 2.1.0 field |

---

## Definition of Done

1. ✅ All existing 31 tests pass (no regressions)
2. ✅ New tests pass (path normalization + fingerprint stability)
3. ✅ Ruff lint passes
4. ✅ Manual verification: feed a sample ZAP JSON through converter, inspect SARIF output
5. ✅ Code review + security review (fingerprint logic, regex patterns)
6. ✅ Committed and pushed
