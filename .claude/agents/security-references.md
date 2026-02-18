# Security Pattern Reference

Detailed checklists and code examples for security reviews.
Referenced by `security-reviewer.md` — read only the sections relevant to the code being reviewed.

---

## [OWASP] OWASP Top 10 Detailed Checklists

### A01: Broken Access Control
- [ ] Authorization checks on all sensitive endpoints via `Depends()`
- [ ] No insecure direct object references (IDOR) — user can't access other users' resources by guessing IDs
- [ ] User can only access their own resources (filter by `user_id` in all queries)
- [ ] Principle of least privilege applied

### A02: Cryptographic Failures
- [ ] No secrets in source code (API keys, passwords, connection strings)
- [ ] No PII in logs (names, emails, phone numbers)
- [ ] Sensitive data not returned in API responses unnecessarily
- [ ] Error messages don't leak internal details (no SQL, paths, stack traces)

### A03: Injection
- [ ] No raw SQL strings or f-string queries (use parameterized queries)
- [ ] No `shell=True` in subprocess calls
- [ ] No unsanitized input in command construction
- [ ] No string concatenation in database queries
- [ ] No unsanitized user input in LLM prompts
- [ ] No XSS (user input escaped before rendering)

### A04: Insecure Design
- [ ] Defense in depth applied (validation at type level + sanitization at use site)
- [ ] Rate limiting on sensitive operations
- [ ] Business logic validated server-side

### A05: Security Misconfiguration
- [ ] CORS properly configured (not `*` in production)
- [ ] Debug mode disabled in production config
- [ ] Security headers present (CSP, X-Frame-Options)

### A06: Vulnerable Components
- [ ] Dependencies scanned for CVEs (pip-audit, npm audit)
- [ ] No outdated packages with known vulnerabilities
- [ ] Minimal dependencies used

### A07: Authentication Failures
- [ ] Endpoints have proper auth via `Depends()`
- [ ] No hardcoded credentials or API keys
- [ ] No credentials in logs or error messages

### A08: Software & Data Integrity Failures
- [ ] No `pickle.loads()` on untrusted data
- [ ] No `yaml.load()` without `Loader=SafeLoader`
- [ ] No `eval()` or `exec()` on user input

### A09: Security Logging & Monitoring Failures
- [ ] Logs don't contain sensitive data
- [ ] Log injection prevented (no unsanitized user input in log format strings)

### A10: Server-Side Request Forgery (SSRF)
- [ ] URLs validated before server-side requests
- [ ] No user-controlled URLs without allowlist

---

## [BACKEND] FastAPI & Python Patterns

### Authentication
```python
# BAD - Missing auth
@router.get("/admin/users")
async def get_users():
    ...

# GOOD - Auth required
@router.get("/admin/users")
async def get_users(user: User = Depends(require_admin)):
    ...
```

### Input Validation
- [ ] Pydantic models validate all input
- [ ] Path parameters validated (UUID, not arbitrary strings)
- [ ] Query parameters validated (type, range, length)
- [ ] Request body size limits enforced

### Error Handling
```python
# BAD - Leaks info
except Exception as e:
    return {"error": str(e)}  # May contain SQL, paths, etc.

# GOOD - Generic error
except Exception as e:
    logger.error(f"Error: {e}")  # Log details server-side
    return {"error": "An error occurred"}  # Generic to client
```

### Command Execution
```python
# BAD - Command injection
subprocess.run(f"convert {filename}", shell=True)

# GOOD - No shell, list args
subprocess.run(["convert", filename], shell=False)
```

### Business Logic
- [ ] Workflow steps cannot be skipped or reordered
- [ ] State transitions validated server-side
- [ ] Negative values handled correctly

### Race Conditions (TOCTOU)
```python
# BAD - Race condition
if user.balance >= amount:
    # Another request could modify balance here!
    user.balance -= amount

# GOOD - Atomic operation
result = await db.execute(
    update(User)
    .where(User.id == user_id, User.balance >= amount)
    .values(balance=User.balance - amount)
)
if result.rowcount == 0:
    raise InsufficientBalance()
```

### Mass Assignment
```python
# BAD - User can set is_admin
class UserCreate(BaseModel):
    class Config:
        extra = "allow"  # Accepts any field!

# GOOD - Explicit fields only
class UserCreate(BaseModel):
    email: str
    password: str
    class Config:
        extra = "forbid"  # Reject unexpected fields
```

---

## [DATABASE] PostgreSQL & SQLAlchemy Patterns

### Query Safety
```python
# BAD - SQL injection
query = f"SELECT * FROM users WHERE id = {user_id}"

# GOOD - ORM parameterized
stmt = select(User).where(User.id == user_id)

# GOOD - text() with params if raw SQL needed
session.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})
```

### Connection Security
- [ ] TLS for database connections
- [ ] Connection string in environment variables (not hardcoded)
- [ ] Least-privilege database user
- [ ] No hardcoded credentials

### Permissions
- [ ] Application uses limited database role
- [ ] Row-level security where appropriate

---

## [LLM] LLM & AI Security Patterns

### Prompt Injection
- [ ] User input separated from system prompts (role-based message structure)
- [ ] Input sanitized via `sanitize_llm_input()` before sending to LLM
- [ ] Feedback sanitized via `sanitize_user_feedback()` before prompt insertion
- [ ] Output validated before use
- [ ] Sensitive data not sent to LLM unnecessarily

```python
# BAD - Direct user input in prompt
prompt = f"Help the user: {user_message}"

# GOOD - Clear separation via role-based messages
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": sanitize_llm_input(user_message)}
]
```

### Regeneration Feedback Security
- [ ] Feedback text length-constrained (MAX_FEEDBACK_LENGTH = 500)
- [ ] Tone overrides length-constrained AND sanitized via `sanitize_llm_input()` (free-text in prompt)
- [ ] Feedback goes through `sanitize_user_feedback()` before prompt insertion
- [ ] Frozen dataclasses use `tuple` not `list` for true immutability

### Collection Sanitization (lists/tuples embedded in prompts)
- [ ] Each element individually sanitized via `sanitize_llm_input()`
- [ ] Collection size capped (e.g., `_MAX_STORIES` for story IDs)
- [ ] Each element length-capped before sanitization (e.g., `sid[:_MAX_STORY_ID_LENGTH]`)
- [ ] Joined result cannot break XML structure (e.g., `</regeneration_context>` in an element)

```python
# BAD — raw user strings joined into prompt
ids_formatted = ", ".join(excluded_story_ids)

# GOOD — per-element sanitize + count cap + length cap
safe_ids = [
    sanitize_llm_input(sid[:_MAX_STORY_ID_LENGTH])
    for sid in excluded_story_ids[:_MAX_STORIES]
]
ids_formatted = ", ".join(safe_ids)
```

### Data Leakage
- [ ] PII not sent to external LLM APIs unnecessarily
- [ ] API keys in environment variables, not in code
- [ ] Rate limits on LLM calls
- [ ] Usage monitored for anomalies

### Output Safety
- [ ] No `eval()`/`exec()` on LLM-generated content
- [ ] Generated content sanitized before display
- [ ] LLM output validated before use (JSON parsing with fallbacks)

### Sanitization Pipeline
This project has a dedicated sanitization pipeline at `backend/app/core/llm_sanitization.py`:
- NFKC → zero-width strip → NFD → combining mark strip → confusable map → control chars → injection patterns → NFC
- All user text MUST pass through `sanitize_llm_input()` before reaching prompts
- Feedback text MUST pass through `sanitize_user_feedback()` (REQ-010 §7.2)

---

## [FUTURE] Frontend, Extension, Sessions & Auth Patterns

> These patterns are NOT active yet. Load this section only when reviewing code in
> `frontend/`, `extension/`, or authentication-related modules.

### Frontend (Next.js / React)
- [ ] No `dangerouslySetInnerHTML` without DOMPurify sanitization
- [ ] User input escaped before rendering (use React's built-in escaping)
- [ ] CSP header configured (no `unsafe-inline`, no `unsafe-eval`)
- [ ] No secrets in localStorage (sensitive data in httpOnly cookies only)
- [ ] Anti-CSRF tokens for state-changing operations
- [ ] SameSite cookie attribute set

### Browser Extension (Chrome Manifest V3)
- [ ] Minimal permissions requested (no `<all_urls>` unless required)
- [ ] Content scripts sandboxed
- [ ] No `eval()` or `innerHTML` with user content
- [ ] Origin validation on message passing
- [ ] No sensitive data in extension storage

### Session Management
- [ ] Session IDs regenerated after login
- [ ] Sessions invalidated on logout and password change
- [ ] Session timeout configured
- [ ] Session fixation prevented

### JWT/Token Security
- [ ] Tokens have expiration (`exp` claim)
- [ ] Algorithm explicitly specified (no `alg: none`)
- [ ] Refresh token rotation implemented
- [ ] Tokens stored securely (httpOnly cookies, not localStorage)
- [ ] Token revocation mechanism exists

### File Upload Security
- [ ] File size limits enforced
- [ ] MIME type validated (not just extension)
- [ ] Filename sanitized (no path traversal via `../`)
- [ ] Files stored as BYTEA in PostgreSQL (project convention — no filesystem paths)

### Other
- [ ] Open redirect: redirect URLs validated against allowlist
- [ ] Timing attacks: constant-time comparison for secrets (`hmac.compare_digest`)
- [ ] Path traversal: `../` sequences blocked, chroot or path prefix enforced
- [ ] Clickjacking: X-Frame-Options and CSP frame-ancestors set

---

## [TOOLS] Automated Tool Reference

### Security Tooling Stack

| Layer | Tool | What It Catches | When It Runs |
|-------|------|-----------------|--------------|
| **SAST (deep)** | **Semgrep Team** | Cross-file taint analysis, FastAPI-native injection detection, 1500+ Pro rules | CI (GitHub Actions) |
| **SAST (fast)** | **Bandit** | Python security patterns (injection, secrets, weak crypto) | Pre-commit hook |
| **Code quality** | **SonarCloud** | Code smells, security hotspots, complexity | CI (post-push) |
| **Dependencies** | **pip-audit** | Known CVEs in Python packages (OSV database) | CI (GitHub Actions) |
| **Dependencies** | **Dependabot** | Automated vulnerability alerts + auto-PRs for pip and GitHub Actions | GitHub (continuous) |
| **Secrets** | **Gitleaks** | Secrets in code (API keys, passwords, tokens) | Pre-commit hook |
| **Fuzz testing** | **Hypothesis** | Property-based fuzz testing for sanitization pipeline invariants | pytest (local + CI) |
| **Linting** | **Ruff** | Linting, import order, unused vars, formatting | Pre-commit hook |
| **Dependencies** | **npm audit** | Known CVEs in JS dependencies | Manual / CI (future) |

### What Each Tool Covers

**Semgrep Team (free for ≤10 contributors):**
- Cross-function, cross-file taint tracking (user input → dangerous sinks)
- FastAPI-native analysis (understands dependency injection, route params, request body)
- SQL injection through ORM layers, SSRF, path traversal, XSS
- Supply chain scanning (dependency CVEs)
- Requires `SEMGREP_APP_TOKEN` secret in GitHub repo settings

**pip-audit (OSV database):**
- Scans full dependency tree including transitive dependencies
- Uses Google's OSV database (broader coverage than PyPI-only)
- Catches CVEs that Dependabot may miss and vice versa (layered defense)

**Dependabot:**
- Automated weekly scans of pip (backend) and GitHub Actions dependencies
- Creates PRs automatically when vulnerable versions detected
- Configured in `.github/dependabot.yml`

### Bandit Error Codes

| Code | Issue | Severity |
|------|-------|----------|
| B101 | assert used (expected in tests) | LOW |
| B102 | exec used | HIGH |
| B103 | set_bad_file_permissions | MEDIUM |
| B104 | bind all interfaces | MEDIUM |
| B105/B106 | Hardcoded passwords | MEDIUM |
| B108 | Insecure temp file | MEDIUM |
| B301 | pickle usage | MEDIUM |
| B303/B324 | MD5/SHA1 for security (use `usedforsecurity=False` for non-crypto) | MEDIUM |
| B307 | eval used | HIGH |
| B602 | subprocess shell=True | HIGH |
| B608 | SQL injection | MEDIUM |

When you find issues that automated tools would also flag, note the code in your review (e.g., `[B602]` for Bandit, `[S5852]` for SonarQube).
