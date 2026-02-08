---
name: zentropy-lint
description: |
  Linting and code quality tooling for Zentropy Scout. Load this skill when:
  - Fixing lint errors or warnings
  - Setting up linters for new code
  - Running pre-commit checks
  - Someone mentions "lint", "ruff", "eslint", "mypy", "prettier", "type check", "bandit", or "security lint"
---

## Zentropy Lint Stack

### Backend (Python)

| Tool | Purpose | Runs Automatically? |
|------|---------|---------------------|
| **Ruff** | Linting + Formatting | ✅ Yes (PostToolUse hook + pre-commit) |
| **mypy** | Static type checking | ❌ Manual |
| **Bandit** | Security linting | ✅ Yes (pre-commit) |
| **Gitleaks** | Secret detection | ✅ Yes (pre-commit) |
| **pip-audit** | Dependency CVE scanning | ❌ Manual / CI |

### Frontend (TypeScript/React)

| Tool | Purpose | Runs Automatically? |
|------|---------|---------------------|
| **ESLint** | Linting | ❌ Manual |
| **Prettier** | Formatting | ❌ Manual |
| **tsc** | Type checking | ❌ Manual |
| **npm audit** | Dependency CVE scanning | ❌ Manual / CI |

---

## Automatic Linting (Hooks)

The following runs automatically after every Python file write/edit:

```bash
ruff check --fix "$FILE" && ruff format "$FILE"
```

This means:
- **You don't need to manually format Python** — it happens on save
- **Auto-fixable lint errors are fixed** — unused imports, sorting, etc.
- **Non-fixable errors will show in output** — you must fix manually

---

## Manual Commands

### Python (Backend)

```bash
# From project root
cd backend

# Full lint check (no auto-fix, see all issues)
ruff check .

# Lint with auto-fix
ruff check --fix .

# Format all files
ruff format .

# Type check (strict)
mypy src/ --strict

# Type check (relaxed, good for incremental adoption)
mypy src/ --ignore-missing-imports
```

### TypeScript/React (Frontend)

```bash
# From project root
cd frontend

# Lint check
npm run lint

# Lint with auto-fix
npm run lint -- --fix

# Format all files
npx prettier --write .

# Type check
npx tsc --noEmit
```

### Full Project Check (Pre-Commit)

```bash
# Run everything before committing
cd backend && ruff check . && mypy src/ --ignore-missing-imports && cd ..
cd frontend && npm run lint && npx tsc --noEmit && cd ..
```

---

## Ruff Configuration

Ruff config lives in `backend/pyproject.toml`:

```toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # Pyflakes
    "I",    # isort (import sorting)
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "UP",   # pyupgrade
    "ARG",  # flake8-unused-arguments
    "SIM",  # flake8-simplify
]
ignore = [
    "E501",  # line too long (handled by formatter)
]

[tool.ruff.lint.isort]
known-first-party = ["app"]
```

---

## Common Lint Errors & Fixes

### Ruff

| Code | Meaning | Fix |
|------|---------|-----|
| `F401` | Unused import | Remove the import or use it |
| `F841` | Unused variable | Remove or prefix with `_` |
| `I001` | Import not sorted | Auto-fixed by `ruff check --fix` |
| `B008` | Function call in default arg | Move to function body |
| `UP035` | Deprecated typing import | Use `from collections.abc import X` |

```python
# F401: Unused import
import os  # Remove if not used

# F841: Unused variable
result = compute()  # Use _result if intentionally unused

# B008: Function call in default argument
# ❌ Bad
def fetch(session: Session = get_session()):
    ...

# ✅ Good
def fetch(session: Session | None = None):
    session = session or get_session()
```

### mypy

| Error | Meaning | Fix |
|-------|---------|-----|
| `[arg-type]` | Wrong argument type | Fix the type or add cast |
| `[return-value]` | Return type mismatch | Fix return or annotation |
| `[no-untyped-def]` | Missing type hints | Add parameter/return types |
| `[union-attr]` | Attribute access on Optional | Add None check first |

```python
# [union-attr]: Item of "str | None" has no attribute "lower"
# ❌ Bad
def process(name: str | None) -> str:
    return name.lower()

# ✅ Good
def process(name: str | None) -> str:
    if name is None:
        return ""
    return name.lower()
```

### ESLint (Frontend)

| Rule | Meaning | Fix |
|------|---------|-----|
| `@typescript-eslint/no-unused-vars` | Unused variable | Remove or prefix with `_` |
| `react-hooks/exhaustive-deps` | Missing dependency | Add to deps array or disable |
| `@typescript-eslint/no-explicit-any` | Using `any` type | Use proper type |

```typescript
// react-hooks/exhaustive-deps
// ❌ Bad
useEffect(() => {
  fetchData(userId);
}, []); // Missing userId

// ✅ Good
useEffect(() => {
  fetchData(userId);
}, [userId]);
```

---

## When to Run What

| Scenario | Command |
|----------|---------|
| Just wrote Python code | Automatic (hook runs) |
| Just wrote TypeScript | `cd frontend && npm run lint` |
| Before committing | Full project check (see above) |
| CI/CD pipeline | `ruff check . && mypy src/ && npm run lint && tsc --noEmit` |
| Fixing reported errors | Run specific tool on specific file |

---

## Ignoring Lint Rules

Sometimes you need to bypass a rule. Use sparingly and document why.

### Ruff (Python)

```python
# Ignore specific line
x = 1  # noqa: F841

# Ignore specific rule for block
# ruff: noqa: E501
long_string = "..."

# Ignore in pyproject.toml (project-wide)
[tool.ruff.lint.per-file-ignores]
"tests/*" = ["ARG"]  # Allow unused args in tests
```

### ESLint (TypeScript)

```typescript
// Ignore next line
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const data: any = response;

// Ignore block
/* eslint-disable react-hooks/exhaustive-deps */
useEffect(() => { ... }, []);
/* eslint-enable react-hooks/exhaustive-deps */
```

---

## Security Linting

Security linters catch vulnerabilities that code-style linters miss.

### Bandit (Python Security)

Bandit finds common security issues in Python code: SQL injection, shell injection, hardcoded passwords, weak crypto, etc.

```bash
# From backend directory
cd backend

# Scan all app code
bandit -r app/

# Scan with config (recommended)
bandit -c pyproject.toml -r app/

# Show only high-severity issues
bandit -r app/ -ll

# Generate report
bandit -r app/ -f json -o bandit-report.json
```

#### Common Bandit Errors

| Code | Severity | Meaning | Fix |
|------|----------|---------|-----|
| `B101` | LOW | Use of assert | Remove assert in production code (OK in tests) |
| `B104` | MEDIUM | Binding to all interfaces | Use specific IP instead of `0.0.0.0` |
| `B105` | MEDIUM | Hardcoded password | Use environment variables |
| `B106` | MEDIUM | Hardcoded password in function arg | Use environment variables |
| `B108` | MEDIUM | Insecure temp file | Use `tempfile.mkstemp()` |
| `B301` | MEDIUM | Pickle usage | Use JSON or safer serialization |
| `B303` | MEDIUM | MD5/SHA1 for security | Use SHA256+ or bcrypt |
| `B307` | MEDIUM | Use of eval() | Never use eval on user input |
| `B602` | HIGH | subprocess with shell=True | Use shell=False with list args |
| `B608` | MEDIUM | SQL injection | Use parameterized queries |

```python
# B602: subprocess with shell=True
# ❌ Bad - shell injection risk
subprocess.run(f"echo {user_input}", shell=True)

# ✅ Good - no shell, list arguments
subprocess.run(["echo", user_input], shell=False)

# B608: SQL injection
# ❌ Bad - string interpolation
query = f"SELECT * FROM users WHERE id = {user_id}"

# ✅ Good - parameterized query
stmt = select(User).where(User.id == user_id)
```

### Gitleaks (Secret Detection)

Gitleaks scans for accidentally committed secrets: API keys, passwords, tokens, private keys.

```bash
# Scan current directory
gitleaks detect --source .

# Scan git history
gitleaks detect --source . --log-opts="--all"

# Generate report
gitleaks detect --source . -r gitleaks-report.json -f json
```

Gitleaks runs automatically on pre-commit. If it blocks your commit:
1. Check the reported file/line
2. Remove the secret from the file
3. Add to `.env` (gitignored) instead
4. If false positive, add to `.gitleaksignore`

### pip-audit (Dependency Vulnerabilities)

Scans installed packages for known CVEs.

```bash
# From backend directory with venv activated
cd backend
source .venv/bin/activate

# Audit current environment
pip-audit

# Audit with auto-fix suggestions
pip-audit --fix --dry-run

# Audit requirements file
pip-audit -r requirements.txt

# JSON output for CI
pip-audit -f json -o audit-report.json
```

### npm audit (Frontend Dependencies)

```bash
# From frontend directory
cd frontend

# Basic audit
npm audit

# Auto-fix where possible
npm audit fix

# Force fix (may have breaking changes)
npm audit fix --force
```

---

## Pre-Commit Security Hooks

These run automatically on every commit:

| Hook | What It Checks |
|------|---------------|
| `bandit` | Python security issues |
| `gitleaks` | Secrets in staged files |
| `detect-private-key` | RSA/SSH private keys |

If a security hook fails, you MUST fix the issue before committing.

---

## Adding New Linters

When adding a new tool:

1. Add to `pyproject.toml` (Python) or `package.json` (JS/TS)
2. Document in this skill file
3. Consider adding to pre-commit hooks
4. Consider adding to PostToolUse hook if it should auto-run on file save
5. Add to CI/CD pipeline
