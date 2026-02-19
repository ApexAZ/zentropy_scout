# REQ-013: Authentication & Account Management

**Status:** Draft
**PRD Reference:** §5 Architecture, §6 Data Strategy
**Last Updated:** 2026-02-18

---

## 1. Overview

This document specifies the authentication system for Zentropy Scout's transition from single-user local mode to a hosted, multi-user service. It covers identity providers, session management, account linking, and the integration points on both the FastAPI backend and Next.js frontend.

**Key Principle:** Authentication answers "who are you?" The existing middleware injection pattern (REQ-006 §2.2) remains unchanged — `get_current_user_id()` swaps from reading an environment variable to reading a JWT cookie. No endpoint code changes.

**Scope:**
- Four identity providers: Google OAuth, LinkedIn OAuth, Email + Password, Magic Link (passwordless)
- Automatic account linking by verified email address
- JWT-in-cookie session strategy (required for SSE compatibility)
- Backend JWT validation in FastAPI
- Frontend login/register UI, route protection, and account management
- Password hashing, strength validation, and reset flow
- Email delivery for magic links and password resets

**Out of scope:** Role-based access control, admin dashboard, API key authentication, Chrome Extension auth (see REQ-011). These are future extensions.

---

## 2. Dependencies

### 2.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-005 Database Schema v0.10 | Schema | Existing `users` table to expand |
| REQ-006 API Contract v0.8 | Integration | Auth middleware pattern (§6.1), CORS config |
| REQ-012 Frontend Application v0.1 | Integration | Auth placeholder (§4.6), onboarding gate |

### 2.2 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-014 Multi-Tenant Isolation | Prerequisite | Tenant isolation requires authenticated user identity |

---

## 3. Design Decisions & Rationale

### 3.1 Auth Library: Auth.js v5

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Auth.js v5 (NextAuth) | ✅ | Purpose-built for Next.js App Router. Handles OAuth flows, CSRF, session management. Built-in account linking. Active community, well-documented. Free and open-source. |
| Lucia Auth | — | Lightweight but discontinued (archived Jan 2025). No longer maintained. |
| Supabase Auth | — | Requires Supabase platform dependency. We use raw PostgreSQL — adding Supabase just for auth is unnecessary coupling. |
| Custom OAuth implementation | — | Significant effort to build securely. OAuth has many edge cases (PKCE, state validation, nonce handling). Auth.js solves these out of the box. |

### 3.2 Session Strategy: JWT in httpOnly Cookie

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| JWT in httpOnly cookie | ✅ | Automatically sent with all requests including EventSource (SSE). No client-side token management. XSS-resistant (JavaScript cannot read httpOnly cookies). FastAPI validates independently with shared secret. |
| Bearer token in Authorization header | — | EventSource API cannot send custom headers — breaks SSE authentication. Requires client-side token storage (localStorage is XSS-vulnerable). |
| Database sessions with session ID cookie | — | Requires database lookup on every request. Higher latency for a system with frequent API calls. Auth.js database sessions add a round-trip per request. |

**Critical constraint:** The frontend SSE client uses the browser's native `EventSource` API (see `frontend/src/lib/sse-client.ts`). `EventSource` does not support custom HTTP headers. Cookies are the only automatic credential mechanism.

### 3.3 Email Delivery: Resend (Recommended)

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Resend | ✅ (Recommended) | Developer-friendly API, generous free tier (100 emails/day), first-class Auth.js integration, React Email for templates. |
| SendGrid | — | More mature but heavier setup. Free tier sufficient (100 emails/day). |
| AWS SES | — | Cheapest at scale but requires AWS account setup, domain verification, and more configuration. Better for high-volume transactional email. |

**Note:** Email provider is a runtime configuration choice. The Auth.js email provider adapter is swappable without code changes.

### 3.4 Password Strategy: Offered Alongside Passwordless

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Password + OAuth + Magic Link (all four) | ✅ | Most users expect a password option — it's the lowest-friction repeat sign-in method (no email round-trip, no OAuth redirect). OAuth is faster for users with Google/LinkedIn accounts. Magic link becomes the password reset mechanism. All four methods complement each other. |
| Passwordless only (OAuth + Magic Link) | — | Magic link requires an email round-trip on every sign-in when session expires. This is real friction, especially on mobile or with slow email delivery. Uncommon outside developer tools and B2B SaaS. |
| Password only | — | No reason to exclude OAuth (zero-effort for users who have Google/LinkedIn). |

**Role of each method:**

| Method | Primary use case |
|--------|-----------------|
| Email + Password | Default sign-in for returning users. Familiar, no external dependency. |
| Google OAuth | One-click sign-in for Google users. Best repeat UX. |
| LinkedIn OAuth | One-click sign-in. Professional identity signal. |
| Magic Link | Account recovery ("forgot password"). Also works as a standalone sign-in for users who prefer passwordless. |

### 3.5 Account Linking Strategy: Automatic by Verified Email

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Automatic linking by verified email | ✅ | Seamless UX — user signs in with Google or LinkedIn using same email, accounts merge automatically. Auth.js supports this natively. No manual "link accounts" UI needed. |
| Manual account linking | — | Requires explicit user action and additional UI. Worse UX for the common case (same person, same email, different provider). |
| No linking (separate accounts per provider) | — | Creates duplicate data. User signs in with Google and LinkedIn — two separate accounts with two separate personas. Confusing and wasteful. |

**Security requirement:** Only link accounts where the email address is **verified** by the identity provider. Unverified emails must not trigger automatic linking (prevents account takeover via email spoofing).

**Pre-hijack defense:** Auth.js must be configured with `allowDangerousEmailAccountLinking: false` (default). When an OAuth provider tries to link to an existing account that was created via magic link, Auth.js must verify: (1) the OAuth provider reports the email as verified, AND (2) the existing account has `email_verified` set. This prevents an attacker from pre-registering with a victim's email via magic link and having the victim's later OAuth login merge into the attacker's account. See [OWASP Account Pre-Hijacking](https://owasp.org/www-community/attacks/Account_Pre-Hijacking).

---

## 4. Identity Providers

### 4.1 Google OAuth

**Protocol:** OAuth 2.0 with PKCE (Authorization Code flow)
**Scopes:** `openid`, `email`, `profile`
**Data received:** `sub` (Google user ID), `email`, `email_verified`, `name`, `picture`

**Configuration:**
```
GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
```

**Callback URL:** `{NEXTAUTH_URL}/api/auth/callback/google`

### 4.2 LinkedIn OAuth

**Protocol:** OAuth 2.0 (Authorization Code flow)
**Scopes:** `openid`, `email`, `profile`
**Data received:** `sub` (LinkedIn member ID), `email`, `email_verified`, `name`, `picture`

**Configuration:**
```
LINKEDIN_CLIENT_ID=<from LinkedIn Developer Portal>
LINKEDIN_CLIENT_SECRET=<from LinkedIn Developer Portal>
```

**Callback URL:** `{NEXTAUTH_URL}/api/auth/callback/linkedin`

**Note:** LinkedIn uses the OpenID Connect (OIDC) protocol ("Sign In with LinkedIn using OpenID Connect"). The older OAuth 2.0 "Sign In with LinkedIn" API is deprecated.

### 4.3 Email + Password

**Protocol:** Standard credential-based authentication
**Flow (Registration):**
1. User enters email, password, and password confirmation on registration form
2. Backend validates password strength (see §10.8)
3. Password hashed with bcrypt (cost factor 12) and stored in `users.password_hash`
4. `email_verified` set to NULL — user must verify email before account linking works
5. Verification email sent (same magic link flow as §4.4)
6. User clicks verification link → `email_verified` set to `now()`

**Flow (Sign-in):**
1. User enters email and password on login page
2. Auth.js Credentials provider calls backend `/api/v1/auth/verify-password` endpoint
3. Backend looks up user by email, verifies bcrypt hash
4. On success: JWT cookie set, session created
5. On failure: generic "Invalid email or password" error (no user enumeration)

**Flow (Password Reset — reuses Magic Link):**
1. User clicks "Forgot password?" on login page
2. Same flow as §4.4 Magic Link — sends email with sign-in link
3. After clicking link and signing in, user is directed to "Change password" on settings page
4. No separate "reset password" form — the magic link IS the recovery mechanism

**Configuration:** No additional env vars — uses existing `AUTH_SECRET` for bcrypt and Resend for emails.

### 4.4 Magic Link (Passwordless Email)

**Protocol:** Passwordless email-based authentication
**Flow:**
1. User enters email address on login page
2. Auth.js generates a unique, time-limited verification token
3. Token is stored in the `verification_tokens` table
4. Email is sent with a sign-in link containing the token
5. User clicks link → Auth.js validates token → session created
6. Token is deleted after use (single-use)

**Dual role:** Magic links serve as both a standalone sign-in method AND the password reset mechanism. Users who set a password can use "Forgot password?" to receive a magic link, sign in, and then change their password from settings.

**Token properties:**
- Expiry: 10 minutes (configurable via `maxAge`)
- Single-use: Deleted immediately upon verification
- Hashed storage: Token stored as hash in database, not plaintext

**Configuration:**
```
EMAIL_FROM=noreply@zentropyscout.com
RESEND_API_KEY=<from Resend dashboard>
```

---

## 5. Account Linking & Unification

### 5.1 Automatic Linking by Verified Email

When a user authenticates with a new provider:

1. Auth.js checks if a `users` record exists with the same email
2. If **yes** and the email is verified by the provider:
   - Create a new `accounts` record linking the provider to the existing user
   - Do **not** create a new `users` record
   - User's session references the original user ID
3. If **no**:
   - Create a new `users` record
   - Create a new `accounts` record
   - User proceeds to onboarding

**Result:** A single `users.id` (UUID) can have multiple `accounts` rows — one per provider. The user's persona, jobs, applications, and all other data remain tied to one identity regardless of which provider they use to sign in.

### 5.2 Edge Cases

| Scenario | Behavior |
|----------|----------|
| Google login with `jane@example.com`, then LinkedIn login with same email | Accounts linked automatically. Same user. |
| Google login with `jane@example.com`, then magic link with same email | Accounts linked. Same user. |
| Register with email+password `jane@example.com`, then Google login with same email | Accounts linked after email is verified. Same user. If email not yet verified, **not linked** — new user created. |
| Google login with `jane@gmail.com`, LinkedIn login with `jane@company.com` | **Not linked.** Different emails = different users. User must use same email on both providers. |
| Provider returns unverified email | **Not linked.** New user created to prevent account takeover. |
| User changes email on Google after initial registration | No effect on existing account. Auth.js matches by `accounts.providerAccountId`, not email, for returning users. Email matching only occurs on first sign-in with a provider. |

### 5.3 Account Table Schema

See §6.2 for the full `accounts` table definition. Each row represents one identity provider connection:

```
accounts
├── userId      → users.id (the unified user identity)
├── provider    → "google" | "linkedin" | "credentials" | "email"
├── providerAccountId → Google sub, LinkedIn sub, or email address
└── (OAuth tokens for refresh — NULL for credentials/email providers)
```

---

## 6. Database Schema Changes

### 6.1 Users Table (Expanded)

The existing `users` table (REQ-005 §4.0) is expanded to support Auth.js:

```sql
-- Existing columns (preserved)
id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
email           VARCHAR(255) UNIQUE NOT NULL,
created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

-- New columns for Auth.js
name            VARCHAR(255),
email_verified  TIMESTAMPTZ,          -- NULL = unverified, timestamp = when verified
image           TEXT,                  -- Profile picture URL from OAuth provider
updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

-- Password auth (§4.3)
password_hash   VARCHAR(255),          -- bcrypt hash. NULL = user registered via OAuth/magic link only.
                                       -- Users who only use OAuth never have a password.

-- Revocation support
token_invalidated_before  TIMESTAMPTZ  -- JWTs issued before this timestamp are rejected.
                                       -- "Sign out everywhere" sets this to now().
                                       -- NULL = no invalidation (all JWTs valid).
```

**Migration notes:**
- Existing user row gets `email_verified = now()` (trusted since admin-created in local mode)
- `name`, `image` are nullable — populated on first OAuth sign-in
- `updated_at` defaults to `now()` for existing rows

### 6.2 Accounts Table (New)

Stores identity provider connections. Multiple rows per user (one per provider).

```sql
CREATE TABLE accounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type                VARCHAR(50) NOT NULL,           -- "oauth" | "email"
    provider            VARCHAR(50) NOT NULL,           -- "google" | "linkedin" | "email"
    provider_account_id VARCHAR(255) NOT NULL,          -- Provider's unique user ID
    refresh_token       TEXT,                           -- OAuth refresh token (encrypted at rest)
    access_token        TEXT,                           -- OAuth access token (encrypted at rest)
    expires_at          INTEGER,                        -- Token expiry (Unix timestamp)
    token_type          VARCHAR(50),                    -- "bearer"
    scope               TEXT,                           -- OAuth scopes granted
    id_token            TEXT,                           -- OIDC ID token
    session_state       TEXT,                           -- Provider session state
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (provider, provider_account_id)
);

CREATE INDEX idx_accounts_user_id ON accounts(user_id);
```

### 6.3 Sessions Table (New)

Auth.js's `@auth/pg-adapter` expects this table to exist in the schema even when using the JWT session strategy. It is not used for request-level authentication (JWTs handle that). It serves as an infrastructure table for the adapter and may be used for future session analytics.

```sql
CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_token   VARCHAR(255) UNIQUE NOT NULL,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires         TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_token ON sessions(session_token);
```

### 6.4 Verification Tokens Table (New)

Stores magic link tokens. Entries are single-use and time-limited.

```sql
CREATE TABLE verification_tokens (
    identifier  VARCHAR(255) NOT NULL,  -- Email address
    token       VARCHAR(255) NOT NULL,  -- Hashed token
    expires     TIMESTAMPTZ NOT NULL,

    UNIQUE (identifier, token)
);
```

**No `id` column** — tokens are looked up by `(identifier, token)` composite key and deleted after use.

### 6.5 Schema Diagram

```
users (expanded)
├── id, email, name, email_verified, image, created_at, updated_at
│
├── 1:N → accounts (NEW)
│         provider connection records (google, linkedin, email)
│
├── 1:N → sessions (NEW)
│         Auth.js session tracking
│
└── 1:N → personas (EXISTING, unchanged)
          user's professional profiles
```

---

## 7. Backend Integration (FastAPI)

### 7.1 JWT Validation

Auth.js signs a JWT and stores it in an httpOnly cookie named `authjs.session-token` (configurable). FastAPI validates this JWT on every request.

**Shared secret:** Auth.js and FastAPI share `AUTH_SECRET` (used by Auth.js to sign JWTs). FastAPI uses this to verify the JWT signature.

**Validation steps:**
1. Read `authjs.session-token` cookie from request
2. Decode JWT using `AUTH_SECRET` (HS256 algorithm)
3. Verify `exp` claim (not expired)
4. Verify `aud` claim equals `"zentropy-scout"` (prevents cross-environment token reuse)
5. Verify `iss` claim equals the configured issuer (prevents cross-service token reuse)
6. Extract `sub` claim (user ID as UUID string)
7. Check `iat` (issued-at) against `users.token_invalidated_before` (revocation check)
8. Return `uuid.UUID(sub)` as the authenticated user ID

**Implementation — updated `get_current_user_id()`:**

```python
# backend/app/api/deps.py

async def get_current_user_id(
    request: Request, db: AsyncSession = Depends(get_db)
) -> uuid.UUID:
    """Extract authenticated user ID from JWT cookie or env var.

    Local mode: reads DEFAULT_USER_ID from settings.
    Hosted mode: validates JWT from httpOnly cookie.
    """
    if not settings.auth_enabled:
        # Local-first mode (existing behavior)
        if settings.default_user_id is None:
            raise HTTPException(status_code=401, detail=UNAUTHORIZED)
        return settings.default_user_id

    # Hosted mode — validate JWT from cookie
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail=UNAUTHORIZED)

    try:
        payload = jwt.decode(
            token,
            settings.auth_secret,
            algorithms=["HS256"],
            audience="zentropy-scout",
            issuer=settings.auth_issuer,
        )
        user_id = uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=401, detail=UNAUTHORIZED) from exc

    # Revocation check — reject JWTs issued before user's invalidation timestamp
    iat = payload.get("iat")
    if iat:
        result = await db.execute(
            select(User.token_invalidated_before).where(User.id == user_id)
        )
        invalidated_before = result.scalar_one_or_none()
        if invalidated_before and iat < invalidated_before.timestamp():
            raise HTTPException(status_code=401, detail=UNAUTHORIZED)

    return user_id
```

**Performance note:** The revocation check adds one lightweight DB query per authenticated request. This can be mitigated with short-TTL in-process caching (e.g., 60-second TTL per user_id) if profiling shows it is a bottleneck.

**No endpoint changes needed.** All existing endpoints already use `CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]`. FastAPI's DI automatically injects the `Request` and `AsyncSession` parameters.

### 7.2 Configuration

New settings in `backend/app/core/config.py`:

```python
# Authentication
auth_enabled: bool = False                              # Toggle local vs hosted mode
auth_secret: str = ""                                   # Shared with Auth.js (AUTH_SECRET)
auth_issuer: str = "zentropy-scout"                     # JWT issuer claim
auth_cookie_name: str = "authjs.session-token"          # Auth.js default cookie name
auth_cookie_secure: bool = True                         # Require HTTPS in production
auth_cookie_samesite: str = "lax"                       # "lax" for same-origin, "none" for cross-subdomain
```

Environment variables:
```
AUTH_ENABLED=true
AUTH_SECRET=<random-32-byte-hex>    # Same value used by Auth.js (AUTH_SECRET env var)
AUTH_ISSUER=zentropy-scout          # JWT issuer claim for cross-environment protection
AUTH_COOKIE_NAME=authjs.session-token
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax            # Set to "none" if backend and frontend are on different subdomains
```

**Note:** Auth.js v5 uses the `AUTH_SECRET` environment variable name (not `NEXTAUTH_SECRET` from v4). Both the frontend and backend must use the same value.

### 7.3 SSE Authentication

The SSE endpoint (`GET /api/v1/chat/stream`) already uses `CurrentUserId` dependency. Since the JWT is in an httpOnly cookie, and cookies are automatically sent with `EventSource` connections (same origin), SSE authentication works without changes.

**CORS requirement:** `allow_credentials=True` is already set in the CORS middleware (see `backend/app/main.py`). This allows cookies to be sent cross-origin.

### 7.4 Rate Limiting Transition

Current rate limiting keys on client IP (`get_remote_address`). In hosted mode, rate limiting should transition to per-user keying to prevent abuse from shared IP addresses (corporate networks, VPNs).

```python
# Future rate limit key function
def get_rate_limit_key(request: Request) -> str:
    if settings.auth_enabled:
        # Key by user ID (extracted from JWT cookie)
        token = request.cookies.get(settings.auth_cookie_name)
        if not token:
            # No cookie when auth is required = unauthenticated request.
            # Return a sentinel key that hits a strict global limit.
            return f"unauth:{get_remote_address(request)}"
        try:
            payload = jwt.decode(
                token, settings.auth_secret, algorithms=["HS256"],
                audience="zentropy-scout", issuer=settings.auth_issuer,
            )
            return f"user:{payload['sub']}"
        except jwt.InvalidTokenError:
            return f"unauth:{get_remote_address(request)}"
    return get_remote_address(request)
```

**Note:** When `auth_enabled=True`, requests without valid JWTs are keyed as `unauth:{ip}` with a stricter global rate limit (e.g., 10 requests/minute vs. 60/minute for authenticated users). This prevents attackers from stripping cookies to bypass per-user rate limits.

### 7.5 Password Endpoints (FastAPI)

Two new endpoints on the backend for password operations. These are called by the Auth.js Credentials provider and the account settings UI.

**Password verification** (called by Auth.js `authorize` callback):

```python
# POST /api/v1/auth/verify-password
# NOT authenticated — called during sign-in before JWT exists.
# Rate-limited: 5 attempts per email per 15 minutes.

class VerifyPasswordRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class VerifyPasswordResponse(BaseModel):
    id: str       # User UUID as string (Auth.js expects string)
    email: str
    name: str | None
    image: str | None

@router.post("/auth/verify-password")
async def verify_password(body: VerifyPasswordRequest, db: AsyncSession = Depends(get_db)):
    user = await user_repo.get_by_email(db, body.email)
    if not user or not user.password_hash:
        # Constant-time comparison even on miss — prevent user enumeration
        bcrypt.checkpw(b"dummy", DUMMY_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not bcrypt.checkpw(body.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return VerifyPasswordResponse(
        id=str(user.id), email=user.email, name=user.name, image=user.image
    )
```

**Password registration:**

```python
# POST /api/v1/auth/register
# NOT authenticated — called during registration.
# Rate-limited: 3 registrations per IP per hour.

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

@router.post("/auth/register", status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check email not already taken
    existing = await user_repo.get_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Validate password strength (see §10.8)
    validate_password_strength(body.password)

    # Hash password (bcrypt, cost factor 12)
    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt(rounds=12))

    user = await user_repo.create(db, email=body.email, password_hash=password_hash.decode())

    # Trigger email verification (magic link) — delegated to Auth.js
    return {"data": {"id": str(user.id), "email": user.email}}
```

**Password change** (authenticated):

```python
# POST /api/v1/auth/change-password
# Authenticated — requires valid JWT.

class ChangePasswordRequest(BaseModel):
    current_password: str | None = None  # NULL if user has no password (OAuth-only)
    new_password: str = Field(min_length=8, max_length=128)

@router.post("/auth/change-password")
async def change_password(
    body: ChangePasswordRequest,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db),
):
    user = await user_repo.get(db, user_id)

    # If user has existing password, verify current password
    if user.password_hash:
        if not body.current_password:
            raise HTTPException(status_code=400, detail="Current password required")
        if not bcrypt.checkpw(body.current_password.encode(), user.password_hash.encode()):
            raise HTTPException(status_code=401, detail="Current password incorrect")

    validate_password_strength(body.new_password)
    new_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt(rounds=12))

    await user_repo.update(db, user_id, password_hash=new_hash.decode())

    # Invalidate all other sessions (force re-login on other devices)
    await user_repo.update(db, user_id, token_invalidated_before=datetime.utcnow())

    return {"data": {"message": "Password updated"}}
```

### 7.6 CORS Updates

For hosted mode, `ALLOWED_ORIGINS` must include the production domain:

```
ALLOWED_ORIGINS=["https://app.zentropyscout.com"]
```

The `SameSite=Lax` cookie attribute (Auth.js default) works with same-site requests. If backend and frontend are on different subdomains, `SameSite=None; Secure` is required.

---

## 8. Frontend Integration (Next.js)

### 8.1 Auth.js v5 Configuration

Auth.js v5 uses the Next.js App Router API routes:

**File:** `frontend/src/app/api/auth/[...nextauth]/route.ts`

```typescript
import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import LinkedIn from "next-auth/providers/linkedin";
import Credentials from "next-auth/providers/credentials";
import Resend from "next-auth/providers/resend";
import PostgresAdapter from "@auth/pg-adapter";

export const { handlers, signIn, signOut, auth } = NextAuth({
    adapter: PostgresAdapter(pool),  // Direct PostgreSQL connection
    providers: [
        Google({ clientId: GOOGLE_CLIENT_ID, clientSecret: GOOGLE_CLIENT_SECRET }),
        LinkedIn({ clientId: LINKEDIN_CLIENT_ID, clientSecret: LINKEDIN_CLIENT_SECRET }),
        Credentials({
            credentials: {
                email: { label: "Email", type: "email" },
                password: { label: "Password", type: "password" },
            },
            async authorize(credentials) {
                // Delegate password verification to FastAPI backend
                const res = await fetch(`${API_URL}/auth/verify-password`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        email: credentials.email,
                        password: credentials.password,
                    }),
                });
                if (!res.ok) return null;  // Invalid credentials
                return await res.json();   // { id, email, name, image }
            },
        }),
        Resend({ from: EMAIL_FROM, apiKey: RESEND_API_KEY }),
    ],
    session: {
        strategy: "jwt",
        maxAge: 7 * 24 * 60 * 60,  // 7 days (not 30 — limits stolen token window)
    },
    callbacks: {
        jwt({ token, user }) {
            if (user) token.sub = user.id;  // Include user UUID in JWT
            token.aud = "zentropy-scout";    // Audience claim — validated by FastAPI
            token.iss = "zentropy-scout";    // Issuer claim — prevents cross-env reuse
            return token;
        },
    },
    pages: {
        signIn: "/login",               // Custom login page
    },
});
```

**Research spike required:** Before implementation, verify `@auth/pg-adapter` compatibility with:
1. **UUID primary keys** — The adapter may generate cuid/nanoid IDs by default. Our schema requires `gen_random_uuid()`. Check if the adapter supports a `generateId` override or if we need to patch the SQL.
2. **snake_case column names** — Our schema uses `provider_account_id`, `session_token`, etc. The adapter may expect camelCase. Verify column name mapping or configure the adapter accordingly.
3. **Custom columns** — Our `users` table has extra columns (`token_invalidated_before`). Verify the adapter doesn't fail on unknown columns.

This spike should be the **first task** in the implementation plan — it determines whether `@auth/pg-adapter` works out of the box or needs a custom adapter.

### 8.2 Login Page

**Route:** `/login`

**Layout:** Full-screen, no app shell (like `/onboarding`).

**Layout:**
```
┌─────────────────────────────────┐
│                                 │
│      [Zentropy Scout Logo]      │
│    AI-Powered Job Assistant     │
│                                 │
│  ┌───────────────────────────┐  │
│  │  Sign in with Google      │  │  ← OAuth button
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │  Sign in with LinkedIn    │  │  ← OAuth button
│  └───────────────────────────┘  │
│                                 │
│  ────── or sign in with ─────── │
│                                 │
│  ┌───────────────────────────┐  │
│  │  Email                    │  │  ← Input
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │  Password                 │  │  ← Input (show/hide toggle)
│  └───────────────────────────┘  │
│                                 │
│  [Forgot password?]             │  ← Triggers magic link flow
│                                 │
│  ┌───────────────────────────┐  │
│  │  Sign In                  │  │  ← Submit button
│  └───────────────────────────┘  │
│                                 │
│  Don't have an account?         │
│  [Create account]               │  ← Links to /register
│                                 │
│  Privacy Policy · Terms         │
└─────────────────────────────────┘
```

**"Forgot password?" flow:** Clicking "Forgot password?" shows a single email input field and a "Send reset link" button. This sends a magic link (§4.4). After clicking the link, the user is signed in and can change their password from settings.

**States:**
- `idle` — Default, all buttons/inputs enabled
- `submitting` — Sign-in in progress, show spinner on submit button
- `magic-link-sent` — "Check your email" confirmation (after "Forgot password?" flow)
- `error` — Invalid credentials or provider error, show message

**Post-authentication redirect:**
- If user has a persona with `onboarding_complete = true` → redirect to `/` (dashboard)
- If user has a persona with `onboarding_complete = false` → redirect to `/onboarding`
- If user has no persona → redirect to `/onboarding`

### 8.3 Register Page

**Route:** `/register`

**Layout:** Full-screen, same styling as login page.

**Layout:**
```
┌─────────────────────────────────┐
│                                 │
│      [Zentropy Scout Logo]      │
│    Create your account          │
│                                 │
│  ┌───────────────────────────┐  │
│  │  Sign up with Google      │  │  ← OAuth (auto-creates account)
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │  Sign up with LinkedIn    │  │  ← OAuth (auto-creates account)
│  └───────────────────────────┘  │
│                                 │
│  ────── or sign up with ─────── │
│                                 │
│  ┌───────────────────────────┐  │
│  │  Email                    │  │
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │  Password                 │  │  ← With strength indicator
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │  Confirm password         │  │
│  └───────────────────────────┘  │
│                                 │
│  Password requirements:         │
│  ✓ At least 8 characters       │
│  ✓ At least one number         │
│  ✓ At least one special char   │
│                                 │
│  ┌───────────────────────────┐  │
│  │  Create Account           │  │
│  └───────────────────────────┘  │
│                                 │
│  Already have an account?       │
│  [Sign in]                      │  ← Links to /login
│                                 │
│  Privacy Policy · Terms         │
└─────────────────────────────────┘
```

**Post-registration flow:**
1. Account created with `email_verified = NULL`
2. Verification email sent (magic link)
3. Show "Check your email to verify your account" message
4. After verification → redirect to `/onboarding`

**OAuth registration:** Clicking "Sign up with Google/LinkedIn" follows the same OAuth flow as the login page. If no account exists, one is created automatically. OAuth providers supply verified email, so no separate verification step.

### 8.3a Account Settings Section

The existing settings page (`/settings`) gains a new "Account" section at the top:

```
┌─────────────────────────────────────────┐
│  Account                                │
│                                         │
│  Email: jane@example.com  ✓ Verified    │
│  Name:  Jane Smith        [Edit]        │
│                                         │
│  Password:                              │
│  ••••••••     [Change password]         │
│  (or "No password set" if OAuth-only)   │
│                                         │
│  Connected providers:                   │
│  ✓ Google (jane@example.com)            │
│  ✓ LinkedIn (jane@example.com)          │
│  + Connect another provider             │
│                                         │
│  ──────────────────────────────────     │
│  [Sign out]  [Sign out of all devices]  │
└─────────────────────────────────────────┘
```

**"Change password" flow:**
1. Click "Change password"
2. Modal or inline form: Current password (if set) + New password + Confirm new password
3. Submit → Backend verifies current password, hashes new one, updates `password_hash`
4. On success: show confirmation toast, invalidate other sessions (`token_invalidated_before = now()`)

**"No password set" case:** Users who registered via OAuth only see "Set a password" instead of "Change password". They can optionally add a password for email+password sign-in as a backup method.

### 8.4 Auth Context Provider

New provider in the React context hierarchy:

```typescript
// frontend/src/lib/auth-provider.tsx
import { SessionProvider } from "next-auth/react";

export function AuthProvider({ children }: { children: ReactNode }) {
    return <SessionProvider>{children}</SessionProvider>;
}
```

**Updated provider stack** (in `frontend/src/app/layout.tsx`):
```
<AuthProvider>              ← NEW (outermost — auth before anything else)
  <QueryProvider>
    <SSEProvider>
      <ChatProvider>
        {children}
      </ChatProvider>
    </SSEProvider>
  </QueryProvider>
</AuthProvider>
```

### 8.5 Auth Hook

```typescript
// Usage in components
import { useSession } from "next-auth/react";

const { data: session, status } = useSession();
// status: "loading" | "authenticated" | "unauthenticated"
// session.user: { id, name, email, image }
```

### 8.6 Protected Routes — Next.js Middleware

**File:** `frontend/src/middleware.ts`

Server-side route protection that runs before any page renders:

```typescript
export { auth as middleware } from "@/lib/auth";

export const config = {
    matcher: [
        // Protect all routes EXCEPT:
        // - /login, /register (auth pages)
        // - /api/auth/* (Auth.js endpoints)
        // - /_next/* (Next.js internals)
        // - /favicon.ico, /robots.txt (static assets)
        "/((?!login|register|api/auth|_next|favicon.ico|robots.txt).*)",
    ],
};
```

**Behavior:** Unauthenticated requests to protected routes receive a 302 redirect to `/login`.

### 8.7 Updated Onboarding Gate

The existing `OnboardingGate` component (REQ-012 §3.3) gains a new layer:

**Current flow:** Persona check → onboarding or dashboard
**New flow:** Auth check (middleware) → Persona check (OnboardingGate) → onboarding or dashboard

The OnboardingGate component itself does not change — it still checks persona status via `usePersonaStatus()`. The auth layer is handled upstream by Next.js middleware.

### 8.8 API Client — No Changes Needed

The existing API client (`frontend/src/lib/api-client.ts`) makes requests using `fetch()`. Since the JWT is stored in an httpOnly cookie with `SameSite=Lax`, the browser automatically includes it with all same-origin requests. **No `Authorization` header injection needed.**

### 8.9 Logout

**Trigger:** "Sign Out" button in settings page or user menu.

**Flow:**
1. Call `signOut()` from Auth.js
2. Auth.js clears the session cookie
3. Auth.js deletes the session from the `sessions` table
4. Clear TanStack Query cache (`queryClient.clear()`)
5. Redirect to `/login`

---

## 9. Migration from Single-User Mode

### 9.1 Feature Flag

Authentication is gated behind `AUTH_ENABLED` (boolean environment variable). This allows:
- **Local development:** `AUTH_ENABLED=false` — existing behavior, `DEFAULT_USER_ID` from env
- **Hosted deployment:** `AUTH_ENABLED=true` — full auth flow

### 9.2 Data Migration

When transitioning from local mode to hosted mode:

1. The existing user row in `users` table remains
2. On first login (OAuth or magic link), Auth.js creates a new user OR matches by email
3. If the existing user's email matches the OAuth/magic link email:
   - Auth.js links the account to the existing user
   - All existing data (personas, jobs, applications) is preserved
4. If emails don't match:
   - New user is created
   - Existing data remains attached to the original user (accessible by signing in with that email)

**No bulk data migration needed.** The `users.id` → `personas.user_id` FK chain handles isolation naturally.

### 9.3 Backward Compatibility

When `AUTH_ENABLED=false`:
- Auth.js routes (`/api/auth/*`) are still mounted but unused
- `get_current_user_id()` reads `DEFAULT_USER_ID` from env (no JWT check)
- Login page is not shown (OnboardingGate handles routing)
- No behavioral changes from current MVP

---

## 10. Security Considerations

### 10.1 Cookie Security

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `httpOnly` | `true` | Prevents JavaScript access (XSS mitigation) |
| `secure` | `true` (production) | Cookie only sent over HTTPS |
| `sameSite` | `lax` | CSRF protection (cookie not sent on cross-origin POST) |
| `path` | `/` | Available to all routes |
| `maxAge` | 7 days | Session duration (reduced from 30 days to limit stolen token window) |

### 10.2 CSRF Protection

**Auth.js endpoints (`/api/auth/*`):** Auth.js v5 includes built-in CSRF protection:
- CSRF token generated per session
- Validated on all state-changing Auth.js endpoints (sign-in, sign-out)
- Token stored in a separate cookie (`authjs.csrf-token`)

**FastAPI API endpoints (`/api/v1/*`):** Not covered by Auth.js CSRF. Protected by the combination of:
- `SameSite=Lax` cookie attribute — prevents cross-site form POSTs
- CORS with `allow_credentials=True` + explicit `ALLOWED_ORIGINS` (not `*`) — prevents cross-origin JavaScript requests
- The browser's Same-Origin Policy blocks cross-origin `fetch()` with credentials unless the server's CORS policy explicitly allows the requesting origin

**CRITICAL:** `ALLOWED_ORIGINS` must never be set to `*` when `allow_credentials=True`. This would allow any website to make authenticated API calls on behalf of the user.

### 10.3 Token Rotation

Auth.js JWT strategy rotates the JWT on every request (new `exp` claim). This limits the window of exposure if a token is compromised.

### 10.4 OAuth Security

- **PKCE** (Proof Key for Code Exchange) is used for all OAuth flows (Auth.js default)
- **State parameter** validated to prevent CSRF on OAuth callbacks
- **Nonce** validated for OIDC providers (Google, LinkedIn)
- OAuth tokens (refresh_token, access_token) encrypted at rest in the `accounts` table

### 10.5 Magic Link Security

- Token expires in 10 minutes
- Single-use (deleted after verification)
- Token hashed before database storage (Auth.js uses 32-byte random tokens = 256 bits entropy)
- Rate-limited: Max 5 magic link requests per email per hour, enforced in Auth.js `sendVerificationRequest` callback (not the email provider — Resend has no per-email rate limiting)
- Also serves as the password reset mechanism — no separate reset token system needed

### 10.6 Token Revocation

JWT strategy means tokens cannot be individually revoked. Mitigations:

1. **Short maxAge (7 days)** — Limits the window if a token is stolen
2. **Token rotation** — Auth.js rotates the JWT on every request (new `exp`, new `iat`). Active users always have fresh tokens.
3. **Invalidation timestamp** — `users.token_invalidated_before` column. "Sign out everywhere" sets this to `now()`. FastAPI checks `iat < token_invalidated_before` on every request and rejects stale JWTs.
4. **Future enhancement:** Switch to short-lived access tokens (15 min) + database-backed refresh tokens for stronger revocation guarantees.

### 10.8 Password Security

**Hashing algorithm:** bcrypt with cost factor 12. bcrypt is purpose-built for password hashing — it's deliberately slow (to resist brute force) and includes a per-password salt automatically.

**Password strength requirements:**

| Rule | Requirement |
|------|-------------|
| Minimum length | 8 characters |
| Maximum length | 128 characters (prevents bcrypt DoS — bcrypt truncates at 72 bytes) |
| Character types | At least one letter, one number, and one special character |
| Breached password check | Reject passwords found in the [Have I Been Pwned](https://haveibeenpwned.com/API/v3#SearchingPwnedPasswordsByRange) Pwned Passwords API (k-anonymity model — only first 5 chars of SHA-1 hash sent, no plaintext exposure) |

**Validation function:**

```python
def validate_password_strength(password: str) -> None:
    """Raise ValidationError if password is too weak."""
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")
    if len(password) > 128:
        raise ValidationError("Password must be at most 128 characters")
    if not re.search(r"[a-zA-Z]", password):
        raise ValidationError("Password must contain at least one letter")
    if not re.search(r"\d", password):
        raise ValidationError("Password must contain at least one number")
    if not re.search(r"[^a-zA-Z\d]", password):
        raise ValidationError("Password must contain at least one special character")
    # Breached password check via HIBP API (k-anonymity)
    if is_password_breached(password):
        raise ValidationError("This password has appeared in a data breach. Please choose a different one.")
```

**Rate limiting on password endpoints:**

| Endpoint | Limit | Key |
|----------|-------|-----|
| `POST /auth/verify-password` | 5 per 15 minutes | Per email address |
| `POST /auth/register` | 3 per hour | Per IP address |
| `POST /auth/change-password` | 5 per hour | Per authenticated user |

**User enumeration prevention:** The `verify-password` endpoint always performs a bcrypt comparison (using a dummy hash on miss) to maintain constant-time response regardless of whether the email exists. The `register` endpoint returns `409 Conflict` for existing emails — this is an acceptable trade-off (email enumeration via registration is a known limitation; mitigated by rate limiting).

### 10.9 Audit Logging

Log the following authentication events for security monitoring (structured JSON logs):

| Event | Data Logged | Log Level |
|-------|-------------|-----------|
| Successful login | user_id, provider, IP, timestamp | INFO |
| Failed login attempt | provider, email (hashed), IP, reason | WARN |
| Account creation (register) | user_id, method (password/oauth), IP | INFO |
| Password changed | user_id, IP, timestamp | INFO |
| Failed password attempt (brute force signal) | email (hashed), IP, attempt count | WARN |
| Account linking | user_id, new provider, IP | INFO |
| Magic link sent | email (hashed), IP, timestamp | INFO |
| Token invalidation ("sign out everywhere") | user_id, IP, timestamp | INFO |
| JWT validation failure | IP, reason (expired/invalid/revoked), timestamp | WARN |

**No PII in logs.** Email addresses are hashed before logging. User IDs are UUIDs (not personally identifying without database access).

---

## 11. Environment Variables Summary

### Backend (`backend/.env`)

```bash
# Existing (unchanged)
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=zentropy_scout
DEFAULT_USER_ID=                        # Still used when AUTH_ENABLED=false

# New
AUTH_ENABLED=true                        # Toggle auth mode
AUTH_SECRET=<random-32-byte-hex>         # Shared with NEXTAUTH_SECRET
```

### Frontend (`frontend/.env`)

```bash
# Existing (unchanged)
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# New (Auth.js v5 uses AUTH_SECRET, not NEXTAUTH_SECRET)
AUTH_URL=http://localhost:3000            # Auth.js v5 base URL (replaces NEXTAUTH_URL)
AUTH_SECRET=<same-as-backend-AUTH_SECRET> # Shared with backend AUTH_SECRET
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
EMAIL_FROM=noreply@zentropyscout.com
RESEND_API_KEY=
```

**Note:** Auth.js v5 uses `AUTH_SECRET` and `AUTH_URL` as environment variable names. The v4 names (`NEXTAUTH_SECRET`, `NEXTAUTH_URL`) are deprecated.

### Operational Notes

**Database connection pools:** Auth.js's `PostgresAdapter(pool)` creates a second database connection pool from the Next.js server process (in addition to FastAPI's pool). Both must be sized appropriately:
- FastAPI pool: `DATABASE_POOL_SIZE` (existing, default 10)
- Auth.js pool: `AUTH_DB_POOL_SIZE` (new, default 5 — auth queries are lightweight)

Ensure the total connections across both pools do not exceed PostgreSQL's `max_connections` setting.

**Auth.js adapter UUID compatibility:** The `@auth/pg-adapter` may generate non-UUID IDs by default (cuid or nanoid). The adapter must be configured to use PostgreSQL's `gen_random_uuid()` for ID generation, matching the existing schema convention. Verify this during implementation by checking the adapter source code or passing a custom `generateId` function.

---

## 12. Open Questions

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | Which email provider for magic links? | Recommended: Resend | See §3.3. Swappable via Auth.js adapter config. |
| 2 | Session duration (maxAge)? | Proposed: 7 days | Reduced from 30 days to limit stolen token exposure. Auth.js token rotation means active users never notice. |
| 3 | Should we support "Sign out of all devices"? | Included (v0.1) | Implemented via `users.token_invalidated_before` column. "Sign out everywhere" sets this to `now()`, rejecting all previously-issued JWTs. See §10.6. |
| 4 | Custom email template for magic links? | Deferred | Use Auth.js default initially. Add branded template when design system is ready. |
| 5 | Should LinkedIn OAuth use basic profile or full profile scope? | Proposed: basic (openid, email, profile) | Full profile requires LinkedIn partner review. Basic is self-serve. |
| 6 | Domain for production (affects OAuth redirect URLs)? | TBD | Needed before registering OAuth apps with Google/LinkedIn. |

---

## 13. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-18 | v0.1 | Initial draft — 3 providers, JWT-in-cookie, account linking |
| 2026-02-18 | v0.2 | Security hardening — JWT revocation (`token_invalidated_before`), `aud`/`iss` claims, pre-hijack defense, CSRF for FastAPI, audit logging, reduced maxAge to 7 days, rate limit key fix, adapter UUID note, connection pool note |
| 2026-02-18 | v0.3 | Added @auth/pg-adapter research spike note to §8.1 — UUID PKs, snake_case columns, custom columns compatibility must be verified before implementation |
| 2026-02-18 | v0.4 | Added email+password as fourth identity provider (§4.3). Added register page (§8.3), account settings section (§8.3a), password endpoints (§7.5), password security (§10.8). Magic link now dual-role: standalone sign-in + password reset. Updated login page with email/password form. Updated scope, design decisions (§3.4), edge cases, users table (password_hash), Auth.js config (Credentials provider), middleware matcher, audit logging. |
