---
name: zentropy-security-alerts
description: |
  Security alert triage protocol for Zentropy Scout. Load this skill when:
  - Triaging GitHub Security tab alerts (ZAP, Semgrep, Dependabot)
  - Dismissing false positive alerts via `gh api`
  - Someone mentions "security alert", "ZAP", "dismiss", "false positive", or "triage"
  - Reviewing DAST/SAST scan results
---

## Purpose & Scope

This skill covers the **alert triage protocol** — how to review, classify, and dismiss security scanner alerts that appear in the GitHub Security tab.

**This skill handles:**
- Triaging code scanning alerts (ZAP DAST, Semgrep SAST)
- Triaging Dependabot vulnerability alerts
- Dismissing false positives via `gh api`
- Querying SonarCloud issues via REST API

**This skill does NOT handle:**
- Manual code review for vulnerabilities — use the `security-reviewer` subagent
- Linter configuration or lint errors — use the `zentropy-lint` skill
- Writing secure code patterns — see CLAUDE.md Critical Rules

---

## Triage Protocol

Follow this exact order for every alert. Never batch-dismiss without individual review.

### Step 1: Query All Open Alerts

```bash
# Code scanning (ZAP + Semgrep + Trivy)
gh api repos/ApexAZ/zentropy_scout/code-scanning/alerts?state=open \
  --jq '.[] | {number, rule: .rule.id, tool: .tool.name, severity: .rule.security_severity_level, message: .most_recent_instance.message.text}'

# Dependabot
gh api repos/ApexAZ/zentropy_scout/dependabot/alerts?state=open \
  --jq '.[] | {number, package: .security_vulnerability.package.name, severity: .severity, summary: .security_advisory.summary}'

# SonarCloud (web API, no gh needed)
# Query: https://sonarcloud.io/api/issues/search?componentKeys=ApexAZ_zentropy_scout&resolved=false
```

### Step 2: Examine Each Alert Individually

For each alert, determine:
1. **What code path is affected?** — Read the flagged file and line
2. **Is the vulnerability reachable?** — Can user input reach the flagged code?
3. **Is there a mitigating control?** — Auth, validation, sanitization upstream?
4. **Is it a scanner limitation?** — Does the tool lack context about the framework?

### Step 3: Classify — Genuine or False Positive

- **Genuine vulnerability** — STOP. Fix the vulnerability before proceeding with any other work. Do not dismiss.
- **False positive** — Dismiss with the appropriate reason and a detailed comment explaining WHY it's a false positive.

### Step 4: Dismiss False Positives via API

See Dismissal Commands below. Always include a `dismissed_comment` explaining the rationale.

### Step 5: Verify

Re-query to confirm the alert count decreased as expected.

---

## Dismissal Commands

### Code Scanning Alerts (ZAP, Semgrep, Trivy)

```bash
# Dismiss a single alert
gh api -X PATCH repos/ApexAZ/zentropy_scout/code-scanning/alerts/{ALERT_NUMBER} \
  -f state=dismissed \
  -f dismissed_reason="false positive" \
  -f dismissed_comment="Explain why this is a false positive"
```

### Dependabot Alerts

```bash
# Dismiss a single alert
gh api -X PATCH repos/ApexAZ/zentropy_scout/dependabot/alerts/{ALERT_NUMBER} \
  -f state=dismissed \
  -f dismissed_reason="tolerable_risk" \
  -f dismissed_comment="Explain why this is acceptable"
```

### SonarCloud Issues

SonarCloud does not support dismissal via CLI. Use the web UI:
1. Navigate to the issue at `https://sonarcloud.io/project/issues?id=ApexAZ_zentropy_scout`
2. Click the issue, select "Resolve as" > "False Positive" or "Won't Fix"
3. Add a comment explaining the rationale

---

## Valid Dismissal Reasons

### Code Scanning (`dismissed_reason`)

| Reason | When to Use |
|--------|-------------|
| `"false positive"` | Scanner is wrong — the vulnerability doesn't exist in context |
| `"won't fix"` | Known limitation, accepted risk with documented justification |
| `"used in tests"` | Code only runs in test environment, not production |

### Dependabot (`dismissed_reason`)

| Reason | When to Use |
|--------|-------------|
| `"fix_started"` | A fix PR is already in progress |
| `"inaccurate"` | The advisory doesn't apply to how we use the package |
| `"no_bandwidth"` | Acknowledged but deferred (use sparingly) |
| `"not_used"` | The vulnerable code path is never invoked |
| `"tolerable_risk"` | Risk accepted — e.g., dev-only dependency, mitigated upstream |

---

## Common False Positive Patterns

ZAP DAST alerts that are typically false positives for API-only applications:

| Rule ID | Alert Name | Why Typically FP |
|---------|------------|------------------|
| `10003` | Vulnerable JS Library | No JS served — API only returns JSON |
| `10020` | Anti-clickjacking Header | API responses, not HTML pages |
| `10035` | Strict-Transport-Security | Only in dev (localhost); prod will have HSTS |
| `10036` | HTTP Only Site | Dev environment uses HTTP; prod uses HTTPS |
| `10038` | Content Security Policy | API returns JSON, not HTML — CSP not applicable |
| `10049` | Non-Storable Content | Caching headers are intentionally permissive for API |
| `10054` | Cookie without SameSite | Auth cookie has SameSite set in production config |
| `10055` | CSP Wildcard | No CSP header needed for JSON API responses |
| `10096` | Timestamp Disclosure | Unix timestamps in API responses are intentional data |
| `10112` | Session Management Response | API session tokens are managed via secure cookies |
| `40012` | Cross Site Scripting (Reflected) | FastAPI auto-escapes; Pydantic validates input |
| `40014` | Cross Site Scripting (Persistent) | Output encoding handled by frontend; API returns JSON |
| `90033` | Loosely Scoped Cookie | Cookie scope is intentionally set for the API domain |
| `100000` | User Agent Fuzzer | Informational — reports server accepts varied User-Agents |

**Important:** Even "typically FP" alerts must be individually verified. A rule that's usually a false positive could be genuine if the code changed.

---

## The zap-rules.tsv Prohibition

**`.github/zap-rules.tsv` must remain empty.** A PreToolUse hook enforces this.

### Why

ZAP's `rules.tsv` file supports `IGNORE` directives that suppress alerts **before** SARIF upload. This means:
- Suppressed alerts never reach the GitHub Security tab
- No human ever sees them
- Genuine vulnerabilities can be silently hidden

This is the opposite of defense-in-depth. The correct approach is:
1. Let ALL alerts flow to the Security tab (no `IGNORE` rules)
2. Review each alert individually using this triage protocol
3. Dismiss false positives via `gh api` with documented rationale
4. Fix genuine vulnerabilities immediately

### What to Do Instead

If a ZAP alert is a false positive:
1. Follow the Triage Protocol above
2. Dismiss via `gh api` with `dismissed_reason` and `dismissed_comment`
3. The dismissal is recorded in GitHub with full audit trail

---

## Relationship to Other Tools

| Tool | Role | How It Relates |
|------|------|----------------|
| `security-reviewer` agent | Pre-commit code review | Catches issues BEFORE they reach CI scanners |
| `zentropy-lint` skill | Local linting (Bandit, Gitleaks) | Fast local checks; this skill handles CI-level alerts |
| Semgrep / ZAP / SonarCloud | CI scanners | Produce the alerts this skill triages |
| Dependabot | Dependency monitoring | Produces alerts this skill triages |
| `.github/zap-rules.tsv` | ZAP config (MUST stay empty) | Never add IGNORE rules — use `gh api` dismissal instead |
