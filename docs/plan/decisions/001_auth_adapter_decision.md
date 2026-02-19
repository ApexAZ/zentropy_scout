# Decision 001: Authentication Adapter Strategy

**Date:** 2026-02-18
**Status:** Proposed
**Phase:** 1 §1 (Research Spike)
**Decision Makers:** User + Claude Code

---

## Context

Phase 1 §1 requires a go/no-go decision on `@auth/pg-adapter` before proceeding with Auth.js v5 integration. This research evaluates three options for the authentication layer.

### Current Environment

| Component | Version |
|-----------|---------|
| Next.js | 16.1.6 |
| React | 19.2.4 |
| FastAPI | 0.115.x |
| PostgreSQL | 16 (pgvector) |
| SQLAlchemy | 2.0+ (async, UUID PKs, snake_case) |

### Requirements (REQ-013)

- UUID primary keys on all tables (except `verification_tokens`)
- snake_case column names throughout
- Custom columns: `password_hash`, `token_invalidated_before` on `users`
- JWT-in-httpOnly-cookie (required for SSE/EventSource)
- 4 providers: Google OAuth, LinkedIn OAuth, Email+Password, Magic Link
- FastAPI validates JWT on every request via `get_current_user_id()`
- Alembic manages all database migrations

---

## Options Evaluated

### Option A: Auth.js v5 + @auth/pg-adapter

**Verdict: NOT RECOMMENDED**

| Criterion | Finding | Risk |
|-----------|---------|------|
| UUID primary keys | Default schema uses SERIAL integers. No config option. Requires forking adapter SQL. | HIGH |
| snake_case columns | Hardcoded mixed camelCase (`"userId"`, `"sessionToken"`) in adapter SQL queries. Cannot be configured. | HIGH |
| Custom user columns | Adapter ignores `password_hash`, `token_invalidated_before`. Custom read/write needed. | MEDIUM |
| Package stability | v5 has **never left beta** (`5.0.0-beta.30`). npm `latest` tag still points to v4.24.13. | HIGH |
| Maintenance status | Auth.js absorbed into Better Auth project (Sep 2025). Now in maintenance mode — security patches only. | HIGH |
| React 19 compatibility | Multiple open issues: `useState` null errors (#12757), URL state bugs (#12711). | MEDIUM |
| Next.js 16 compatibility | Peer dep installation issues reported (#13302). Middleware renamed to `proxy.ts`. | MEDIUM |

**Bottom line:** The adapter would require a complete fork to support UUID PKs + snake_case. Combined with Auth.js being in maintenance mode and v5 never reaching stable, this creates unacceptable long-term maintenance risk.

### Option B: Better Auth

**Verdict: NOT RECOMMENDED**

| Criterion | Finding | Risk |
|-----------|---------|------|
| UUID primary keys | Supported via `advanced.database.generateId: "uuid"` config | LOW |
| snake_case columns | Field mapping supported but has documented bugs (#3212, #3774) | MEDIUM |
| Split architecture | Designed for Next.js monolith. Creates two "backends" (Better Auth + FastAPI). | HIGH |
| Password ownership | Stores passwords in `account` table, not `users`. Conflicts with FastAPI owning `password_hash`. | HIGH |
| Migration systems | Better Auth CLI + Alembic on same DB = two migration systems | HIGH |
| OAuth providers | Google + LinkedIn built-in | LOW |
| React 19 | Webpack alias workaround needed (#5458) | MEDIUM |
| Maturity | v1.0 (Nov 2024), ~25K stars, 600K+/week downloads | MEDIUM |

**Bottom line:** Architectural mismatch. Better Auth wants to be the backend for auth, but FastAPI already is. Two migration systems, two sources of truth for users, and password ownership conflict make this a poor fit for a split Next.js + FastAPI architecture.

### Option C: Custom Implementation (FastAPI-owned auth)

**Verdict: RECOMMENDED**

| Criterion | Finding | Risk |
|-----------|---------|------|
| UUID primary keys | Full control — Alembic migration uses `gen_random_uuid()` | NONE |
| snake_case columns | Full control — matches existing schema conventions | NONE |
| Custom user columns | Full control — `password_hash`, `token_invalidated_before` in `users` table | NONE |
| Split architecture | Perfect fit — FastAPI is single source of truth for all auth | NONE |
| Migration systems | Alembic only — single migration system | NONE |
| JWT-in-cookie | PyJWT + FastAPI middleware — straightforward | LOW |
| OAuth providers | `httpx-oauth` library or manual OAuth2 flow via `httpx` | MEDIUM |
| SSE compatibility | httpOnly cookie sent automatically by browser | NONE |
| Maintenance | No framework dependency for auth — you own the code | LOW |

**Architecture:**

```
Browser
  ├─ Next.js (frontend only)
  │   ├─ Login/Register pages → call FastAPI auth endpoints
  │   ├─ middleware.ts → reads JWT cookie, validates expiry client-side
  │   └─ SessionProvider → context from cookie claims (no server call per page)
  │
  └─ FastAPI (backend — single source of truth)
      ├─ POST /auth/register → create user, hash password, set JWT cookie
      ├─ POST /auth/verify-password → verify credentials, set JWT cookie
      ├─ POST /auth/change-password → update hash, invalidate old JWTs
      ├─ GET /auth/providers/google → redirect to Google OAuth
      ├─ GET /auth/callback/google → exchange code, create/link user, set JWT cookie
      ├─ POST /auth/logout → clear cookie
      ├─ POST /auth/magic-link → send email with login link
      └─ GET /auth/verify-magic-link → verify token, set JWT cookie
```

---

## Recommendation

**Implement Option C: Custom FastAPI-owned authentication.**

### Rationale

1. **Single source of truth.** FastAPI already owns users, personas, job postings. Auth should live there too, not in a separate system.

2. **Single migration system.** Alembic manages everything. No coordination with an external auth library's schema expectations.

3. **Full schema control.** UUID PKs, snake_case, custom columns — no adapter compatibility issues.

4. **No abandoned dependency risk.** Auth.js is in maintenance mode. Better Auth is 15 months old. A custom implementation has zero dependency on external auth framework release cycles.

5. **JWT-in-cookie is simple.** PyJWT encodes/decodes. FastAPI sets the httpOnly cookie on auth responses. The browser sends it automatically. Next.js middleware reads it for client-side route protection.

6. **OAuth is manageable.** Google and LinkedIn OAuth are well-documented REST APIs. The `httpx-oauth` library provides async OAuth2 clients, or manual implementation with `httpx` is ~50 lines per provider.

### Trade-offs Accepted

| Trade-off | Mitigation |
|-----------|------------|
| More upfront code for OAuth flows | `httpx-oauth` library reduces boilerplate; only 2 providers needed |
| No auth library's built-in CSRF protection | FastAPI + SameSite cookie + origin header validation |
| No auth library's built-in rate limiting | Already implemented in `rate_limiting.py` |
| Magic link email sending | Resend API (simple REST call) |

### Impact on Implementation Plan

Phase 1 (backend) is **largely unchanged** — the plan already has JWT validation, password endpoints, UserRepository, and CORS tasks that don't depend on Auth.js.

Phase 2 (frontend) **changes significantly**:
- **Remove:** `next-auth` and `@auth/pg-adapter` dependencies entirely
- **Remove:** Auth.js route handler (`app/api/auth/[...nextauth]/route.ts`)
- **Remove:** Auth.js `SessionProvider`, `useSession()` hook
- **Add:** Custom `SessionProvider` that reads JWT claims from a cookie
- **Add:** Custom `useSession()` hook (thin wrapper around context)
- **Add:** FastAPI OAuth endpoints (Google + LinkedIn) — move to Phase 1 or early Phase 2
- **Keep:** Login/Register pages (form + API calls — simpler without Auth.js abstractions)
- **Keep:** Middleware for route protection (reads JWT cookie directly instead of `auth()`)
- **Keep:** API client `credentials: 'include'` + 401 redirect

The net effect is **less code, fewer dependencies, and simpler debugging** compared to wrapping Auth.js.

---

## Decision

**Approved (2026-02-19).** Proceeding with Option C (custom implementation).

Changes applied:
1. REQ-013 rewritten (v0.5) — all Auth.js references removed, custom FastAPI auth throughout
2. OAuth + magic link endpoints added to Phase 1 (§7, §8)
3. Phase 2 rewritten for custom SessionProvider + forms + middleware (no `next-auth` dependency)
4. All auth logic centralized in FastAPI
