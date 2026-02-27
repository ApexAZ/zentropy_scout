# REQ-013: Authentication & Account Management

**Status:** Implemented
**PRD Reference:** §5 Architecture, §6 Data Strategy
**Last Updated:** 2026-02-27

---

## 1. Overview

This document specifies the authentication system for Zentropy Scout's transition from single-user local mode to a hosted, multi-user service. It covers identity providers, session management, account linking, and the integration points on both the FastAPI backend and Next.js frontend.

**Key Principle:** Authentication answers "who are you?" The existing middleware injection pattern (REQ-006 §2.2) remains unchanged — `get_current_user_id()` swaps from reading an environment variable to reading a JWT cookie. No endpoint code changes.

**Scope:**
- Four identity providers: Google OAuth, LinkedIn OAuth, Email + Password, Magic Link (passwordless)
- Automatic account linking by verified email address
- JWT-in-cookie session strategy (required for SSE compatibility)
- Backend JWT issuance and validation in FastAPI
- Frontend login/register UI, route protection, and account management
- Password hashing, strength validation, and reset flow
- Email delivery for magic links and email verification

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

### 3.1 Auth Architecture: Custom FastAPI-Owned Implementation

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Custom FastAPI implementation | ✅ | FastAPI is the single source of truth for users, sessions, and passwords. Single migration system (Alembic). Full control over UUID PKs, snake_case columns, and custom columns. No dependency on external auth framework release cycles. JWT-in-cookie issuance is straightforward with PyJWT. OAuth flows are well-documented REST APIs (~80 lines per provider). |
| Auth.js v5 (NextAuth) | — | `@auth/pg-adapter` incompatible with UUID PKs and snake_case columns (requires full fork). Auth.js v5 never left beta (`5.0.0-beta.30`). Now in maintenance mode under Better Auth team (Sep 2025). Known React 19 and Next.js 16 issues. Creates split architecture problems (two backends, two migration systems). See `docs/plan/decisions/001_auth_adapter_decision.md`. |
| Better Auth | — | Architectural mismatch with split Next.js + FastAPI architecture. Stores passwords in `account` table (conflicts with FastAPI owning `password_hash`). Would require two migration systems (Better Auth CLI + Alembic) on one database. Custom column naming has documented bugs. |
| Lucia Auth | — | Lightweight but discontinued (archived Jan 2025). No longer maintained. |
| Supabase Auth | — | Requires Supabase platform dependency. We use raw PostgreSQL — adding Supabase just for auth is unnecessary coupling. |

### 3.2 Session Strategy: JWT in httpOnly Cookie

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| JWT in httpOnly cookie | ✅ | Automatically sent with all requests including EventSource (SSE). No client-side token management. XSS-resistant (JavaScript cannot read httpOnly cookies). FastAPI issues and validates independently. |
| Bearer token in Authorization header | — | EventSource API cannot send custom headers — breaks SSE authentication. Requires client-side token storage (localStorage is XSS-vulnerable). |
| Database sessions with session ID cookie | — | Requires database lookup on every request. Higher latency for a system with frequent API calls. |

**Critical constraint:** The frontend SSE client uses the browser's native `EventSource` API (see `frontend/src/lib/sse-client.ts`). `EventSource` does not support custom HTTP headers. Cookies are the only automatic credential mechanism.

### 3.3 Email Delivery: Resend (Recommended)

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Resend | ✅ (Recommended) | Developer-friendly REST API, generous free tier (100 emails/day), simple integration via `httpx`, React Email for templates. |
| SendGrid | — | More mature but heavier setup. Free tier sufficient (100 emails/day). |
| AWS SES | — | Cheapest at scale but requires AWS account setup, domain verification, and more configuration. Better for high-volume transactional email. |

**Note:** Email provider is a runtime configuration choice. The email sending function is a simple HTTP POST — swappable without code changes.

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
| Automatic linking by verified email | ✅ | Seamless UX — user signs in with Google or LinkedIn using same email, accounts merge automatically. No manual "link accounts" UI needed. |
| Manual account linking | — | Requires explicit user action and additional UI. Worse UX for the common case (same person, same email, different provider). |
| No linking (separate accounts per provider) | — | Creates duplicate data. User signs in with Google and LinkedIn — two separate accounts with two separate personas. Confusing and wasteful. |

**Security requirement:** Only link accounts where the email address is **verified** by the identity provider. Unverified emails must not trigger automatic linking (prevents account takeover via email spoofing).

**Pre-hijack defense:** When an OAuth provider tries to link to an existing account, the system must verify: (1) the OAuth provider reports the email as verified, AND (2) the existing account has `email_verified` set. This prevents an attacker from pre-registering with a victim's email via magic link and having the victim's later OAuth login merge into the attacker's account. See [OWASP Account Pre-Hijacking](https://owasp.org/www-community/attacks/Account_Pre-Hijacking).

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

**Callback URL:** `{API_BASE_URL}/api/v1/auth/callback/google`

**Flow:**
1. Frontend links to `GET /api/v1/auth/providers/google` with optional `redirect_uri` query param
2. FastAPI generates PKCE code verifier + challenge, state parameter, stores in server-side session
3. FastAPI redirects to Google's authorization endpoint with PKCE challenge
4. User consents on Google
5. Google redirects to `GET /api/v1/auth/callback/google` with authorization code
6. FastAPI exchanges code for tokens using PKCE verifier
7. FastAPI fetches user info from Google's userinfo endpoint
8. FastAPI creates/links user account (see §5), issues JWT cookie
9. FastAPI redirects to frontend (`/` or `/onboarding`)

### 4.2 LinkedIn OAuth

**Protocol:** OAuth 2.0 (Authorization Code flow) with OpenID Connect
**Scopes:** `openid`, `email`, `profile`
**Data received:** `sub` (LinkedIn member ID), `email`, `email_verified`, `name`, `picture`

**Configuration:**
```
LINKEDIN_CLIENT_ID=<from LinkedIn Developer Portal>
LINKEDIN_CLIENT_SECRET=<from LinkedIn Developer Portal>
```

**Callback URL:** `{API_BASE_URL}/api/v1/auth/callback/linkedin`

**Note:** LinkedIn uses the OpenID Connect (OIDC) protocol ("Sign In with LinkedIn using OpenID Connect"). The older OAuth 2.0 "Sign In with LinkedIn" API is deprecated.

**Flow:** Same as Google (§4.1) with LinkedIn-specific endpoints.

### 4.3 Email + Password

**Protocol:** Standard credential-based authentication
**Flow (Registration):**
1. User enters email, password, and password confirmation on registration form
2. Frontend calls `POST /api/v1/auth/register`
3. Backend validates password strength (see §10.8)
4. Backend checks HIBP breach database (k-anonymity)
5. Password hashed with bcrypt (cost factor 12) and stored in `users.password_hash`
6. `email_verified` set to NULL — user must verify email before account linking works
7. Verification email sent (magic link to verify email address)
8. User clicks verification link → `email_verified` set to `now()`

**Flow (Sign-in):**
1. User enters email and password on login page
2. Frontend calls `POST /api/v1/auth/verify-password`
3. Backend looks up user by email, verifies bcrypt hash
4. On success: JWT cookie set in response, frontend redirects
5. On failure: generic "Invalid email or password" error (no user enumeration)

**Flow (Password Reset — reuses Magic Link):**
1. User clicks "Forgot password?" on login page
2. Frontend calls `POST /api/v1/auth/magic-link` with user's email
3. Same flow as §4.4 Magic Link — sends email with sign-in link
4. After clicking link and signing in, user is directed to "Change password" on settings page
5. No separate "reset password" form — the magic link IS the recovery mechanism

### 4.4 Magic Link (Passwordless Email)

**Protocol:** Passwordless email-based authentication
**Flow:**
1. User enters email address on login page and clicks "Send magic link"
2. Frontend calls `POST /api/v1/auth/magic-link`
3. FastAPI generates a unique, time-limited verification token
4. Token hash is stored in the `verification_tokens` table
5. Email is sent via Resend with a sign-in link containing the token
6. User clicks link → frontend redirects to `GET /api/v1/auth/verify-magic-link?token=...&identifier=...`
7. FastAPI validates token → JWT cookie set → redirect to app
8. Token is deleted after use (single-use)

**Dual role:** Magic links serve as both a standalone sign-in method AND the password reset mechanism. Users who set a password can use "Forgot password?" to receive a magic link, sign in, and then change their password from settings.

**Token properties:**
- Expiry: 10 minutes
- Single-use: Deleted immediately upon verification
- Hashed storage: Token stored as hash in database, not plaintext
- Entropy: 32-byte random token (256 bits)

**Configuration:**
```
EMAIL_FROM=noreply@zentropyscout.com
RESEND_API_KEY=<from Resend dashboard>
```

---

## 5. Account Linking & Unification

### 5.1 Automatic Linking by Verified Email

When a user authenticates with a new provider:

1. FastAPI checks if a `users` record exists with the same email
2. If **yes** and the email is verified by the provider:
   - Create a new `accounts` record linking the provider to the existing user
   - Do **not** create a new `users` record
   - JWT references the original user ID
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
| User changes email on Google after initial registration | No effect on existing account. FastAPI matches by `accounts.provider_account_id`, not email, for returning users. Email matching only occurs on first sign-in with a provider. |

### 5.3 Account Table Schema

See §6.2 for the full `accounts` table definition. Each row represents one identity provider connection:

```
accounts
├── user_id             → users.id (the unified user identity)
├── provider            → "google" | "linkedin" | "credentials" | "email"
├── provider_account_id → Google sub, LinkedIn sub, or email address
└── (OAuth tokens for refresh — NULL for credentials/email providers)
```

---

## 6. Database Schema Changes

### 6.1 Users Table (Expanded)

The existing `users` table (REQ-005 §4.0) is expanded to support authentication:

```sql
-- Existing columns (preserved)
id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
email           VARCHAR(255) UNIQUE NOT NULL,
created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

-- New columns for auth
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
    type                VARCHAR(50) NOT NULL,           -- "oauth" | "email" | "credentials"
    provider            VARCHAR(50) NOT NULL,           -- "google" | "linkedin" | "email" | "credentials"
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

Tracks active sessions for session management and "sign out everywhere" functionality. Each JWT issuance creates a session record. Used for listing active sessions and bulk revocation.

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
│         provider connection records (google, linkedin, email, credentials)
│
├── 1:N → sessions (NEW)
│         active session tracking
│
└── 1:N → personas (EXISTING, unchanged)
          user's professional profiles
```

---

## 7. Backend Integration (FastAPI)

### 7.1 JWT Issuance and Validation

FastAPI is the single authority for JWT issuance and validation. JWTs are stored in an httpOnly cookie named `zentropy.session-token` (configurable).

**JWT issuance (on successful authentication):**
1. Generate JWT with claims: `sub` (user UUID), `aud` ("zentropy-scout"), `iss` (configurable issuer), `exp` (7 days), `iat` (now)
2. Sign with `AUTH_SECRET` using HS256 algorithm
3. Set as httpOnly, Secure, SameSite=Lax cookie in response

**JWT validation (on every authenticated request):**
1. Read `zentropy.session-token` cookie from request
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
auth_secret: str = ""                                   # JWT signing secret
auth_issuer: str = "zentropy-scout"                     # JWT issuer claim
auth_cookie_name: str = "zentropy.session-token"        # Cookie name for JWT
auth_cookie_secure: bool = True                         # Require HTTPS in production
auth_cookie_samesite: str = "lax"                       # "lax" for same-origin, "none" for cross-subdomain
auth_cookie_domain: str = ""                            # Cookie domain (empty = request origin)

# OAuth Providers
google_client_id: str = ""
google_client_secret: str = ""
linkedin_client_id: str = ""
linkedin_client_secret: str = ""

# Email
email_from: str = "noreply@zentropyscout.com"
resend_api_key: str = ""

# Frontend URL (for OAuth redirects back to frontend)
frontend_url: str = "http://localhost:3000"
```

Environment variables:
```
AUTH_ENABLED=true
AUTH_SECRET=<random-32-byte-hex>
AUTH_ISSUER=zentropy-scout
AUTH_COOKIE_NAME=zentropy.session-token
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=

EMAIL_FROM=noreply@zentropyscout.com
RESEND_API_KEY=

FRONTEND_URL=http://localhost:3000
```

### 7.3 SSE Authentication

The SSE endpoint (`GET /api/v1/chat/stream`) already uses `CurrentUserId` dependency. Since the JWT is in an httpOnly cookie, and cookies are automatically sent with `EventSource` connections (same origin), SSE authentication works without changes.

**CORS requirement:** `allow_credentials=True` is already set in the CORS middleware (see `backend/app/main.py`). This allows cookies to be sent cross-origin.

### 7.4 Rate Limiting Transition

Current rate limiting keys on client IP (`get_remote_address`). In hosted mode, rate limiting should transition to per-user keying to prevent abuse from shared IP addresses (corporate networks, VPNs).

```python
# Future rate limit key function
def get_rate_limit_key(request: Request) -> str:
    if settings.auth_enabled:
        token = request.cookies.get(settings.auth_cookie_name)
        if not token:
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

### 7.5 Auth Endpoints (FastAPI)

All auth endpoints live under `/api/v1/auth/` in a dedicated router.

**Password verification:**

```python
# POST /api/v1/auth/verify-password
# NOT authenticated — called during sign-in before JWT exists.
# Rate-limited: 5 attempts per email per 15 minutes.
# On success: sets JWT httpOnly cookie in response.

class VerifyPasswordRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

@router.post("/auth/verify-password")
async def verify_password(body: VerifyPasswordRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await user_repo.get_by_email(db, body.email)
    if not user or not user.password_hash:
        # Constant-time comparison even on miss — prevent user enumeration
        bcrypt.checkpw(b"dummy", DUMMY_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not bcrypt.checkpw(body.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Issue JWT and set cookie
    token = create_jwt(user_id=str(user.id))
    set_auth_cookie(response, token)

    return {"data": {"id": str(user.id), "email": user.email, "name": user.name}}
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
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    # Check email not already taken
    existing = await user_repo.get_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Validate password strength (see §10.8)
    validate_password_strength(body.password)

    # Check HIBP breach database
    if await is_password_breached(body.password):
        raise HTTPException(status_code=422, detail="This password has appeared in a data breach")

    # Hash password (bcrypt, cost factor 12)
    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt(rounds=12))

    user = await user_repo.create(db, email=body.email, password_hash=password_hash.decode())

    # Send verification email (magic link)
    await send_verification_email(user.email)

    return {"data": {"id": str(user.id), "email": user.email}}
```

**Password change** (authenticated):

```python
# POST /api/v1/auth/change-password
# Authenticated — requires valid JWT.
# Rate-limited: 5 per hour per user.

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

**OAuth initiation:**

```python
# GET /api/v1/auth/providers/{provider}
# Redirects to OAuth provider's authorization URL.
# Supports: "google", "linkedin"

@router.get("/auth/providers/{provider}")
async def oauth_initiate(provider: str, request: Request):
    # Generate PKCE code verifier + challenge
    # Generate state parameter, store in server-side session
    # Redirect to provider's authorization endpoint
    ...
```

**OAuth callback:**

```python
# GET /api/v1/auth/callback/{provider}
# Handles OAuth provider redirect after user consent.
# Exchanges code for tokens, fetches user info, creates/links account.

@router.get("/auth/callback/{provider}")
async def oauth_callback(provider: str, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    # Validate state parameter
    # Exchange authorization code for tokens (using PKCE verifier)
    # Fetch user info from provider
    # Create or link user account (§5 account linking logic)
    # Issue JWT and set cookie
    # Redirect to frontend (/ or /onboarding)
    ...
```

**Magic link:**

```python
# POST /api/v1/auth/magic-link
# Sends a magic link email for passwordless sign-in.
# Rate-limited: 5 per email per hour.

class MagicLinkRequest(BaseModel):
    email: EmailStr

@router.post("/auth/magic-link")
async def send_magic_link(body: MagicLinkRequest, db: AsyncSession = Depends(get_db)):
    # Always return success (prevent email enumeration)
    # Generate token, hash it, store in verification_tokens
    # Send email via Resend
    return {"data": {"message": "If an account exists, a sign-in link has been sent"}}
```

**Magic link verification:**

```python
# GET /api/v1/auth/verify-magic-link
# Verifies a magic link token and signs the user in.

@router.get("/auth/verify-magic-link")
async def verify_magic_link(token: str, identifier: str, response: Response, db: AsyncSession = Depends(get_db)):
    # Look up token hash in verification_tokens
    # Verify not expired
    # Delete token (single-use)
    # Set email_verified if not already set
    # Issue JWT and set cookie
    # Redirect to frontend
    ...
```

**Logout:**

```python
# POST /api/v1/auth/logout
# Clears the auth cookie.

@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(settings.auth_cookie_name)
    return {"data": {"message": "Signed out"}}
```

**Session info:**

```python
# GET /api/v1/auth/me
# Returns current user's session info. Used by frontend SessionProvider.
# Returns 401 if no valid JWT.

@router.get("/auth/me")
async def get_me(user_id: CurrentUserId, db: AsyncSession = Depends(get_db)):
    user = await user_repo.get(db, user_id)
    return {"data": {"id": str(user.id), "email": user.email, "name": user.name, "image": user.image}}
```

### 7.6 CORS Updates

For hosted mode, `ALLOWED_ORIGINS` must include the production domain:

```
ALLOWED_ORIGINS=["https://app.zentropyscout.com"]
```

The `SameSite=Lax` cookie attribute works with same-site requests. If backend and frontend are on different subdomains, `SameSite=None; Secure` is required.

**CRITICAL:** `ALLOWED_ORIGINS` must never be set to `*` when `allow_credentials=True`. This would allow any website to make authenticated API calls on behalf of the user.

---

## 8. Frontend Integration (Next.js)

### 8.1 Architecture

The frontend has **no auth library dependency**. All authentication is handled by the FastAPI backend:
- Login/register pages call FastAPI auth endpoints via `api-client.ts`
- JWT cookie is set by FastAPI responses (httpOnly — invisible to JavaScript)
- Next.js middleware reads the JWT cookie to determine route access
- A lightweight `SessionProvider` context provides user info to React components

**No `next-auth`, `@auth/pg-adapter`, or `better-auth` packages are installed.**

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
│  │  Sign in with Google      │  │  ← Links to /api/v1/auth/providers/google
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │  Sign in with LinkedIn    │  │  ← Links to /api/v1/auth/providers/linkedin
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
│  │  Sign In                  │  │  ← Calls POST /auth/verify-password
│  └───────────────────────────┘  │
│                                 │
│  Don't have an account?         │
│  [Create account]               │  ← Links to /register
│                                 │
│  Privacy Policy · Terms         │
└─────────────────────────────────┘
```

**"Forgot password?" flow:** Clicking "Forgot password?" shows a single email input field and a "Send reset link" button. This calls `POST /api/v1/auth/magic-link`. After clicking the link, the user is signed in and can change their password from settings.

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
│  │  Sign up with Google      │  │  ← Links to /api/v1/auth/providers/google
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │  Sign up with LinkedIn    │  │  ← Links to /api/v1/auth/providers/linkedin
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
│  │  Create Account           │  │  ← Calls POST /auth/register
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

**OAuth registration:** Clicking "Sign up with Google/LinkedIn" links to the same OAuth initiation endpoint as the login page. If no account exists, one is created automatically. OAuth providers supply verified email, so no separate verification step.

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
3. Submit → Calls `POST /api/v1/auth/change-password`
4. On success: show confirmation toast, invalidate other sessions (`token_invalidated_before = now()`)

**"No password set" case:** Users who registered via OAuth only see "Set a password" instead of "Change password". They can optionally add a password for email+password sign-in as a backup method.

### 8.4 Auth Context Provider

Custom provider using FastAPI's `/auth/me` endpoint:

```typescript
// frontend/src/lib/auth-provider.tsx

interface Session {
    user: { id: string; email: string; name: string | null; image: string | null };
}

type SessionStatus = "loading" | "authenticated" | "unauthenticated";

const AuthContext = createContext<{ session: Session | null; status: SessionStatus }>({
    session: null,
    status: "loading",
});

export function AuthProvider({ children }: { children: ReactNode }) {
    // On mount: call GET /api/v1/auth/me
    // If 200: set session + status = "authenticated"
    // If 401: set session = null + status = "unauthenticated"
    // Provide context to children
    return <AuthContext.Provider value={{ session, status }}>{children}</AuthContext.Provider>;
}

export function useSession() {
    return useContext(AuthContext);
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
import { useSession } from "@/lib/auth-provider";

const { session, status } = useSession();
// status: "loading" | "authenticated" | "unauthenticated"
// session?.user: { id, name, email, image }
```

### 8.6 Protected Routes — Next.js Middleware

**File:** `frontend/src/middleware.ts`

Server-side route protection that runs before any page renders:

```typescript
import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
    const token = request.cookies.get("zentropy.session-token");
    if (!token) {
        return NextResponse.redirect(new URL("/login", request.url));
    }
    // Optionally: decode JWT to check exp (without full validation — that's FastAPI's job)
    return NextResponse.next();
}

export const config = {
    matcher: [
        // Protect all routes EXCEPT:
        // - /login, /register (auth pages)
        // - /api/* (API routes handled by backend)
        // - /_next/* (Next.js internals)
        // - /favicon.ico, /robots.txt (static assets)
        "/((?!login|register|api|_next|favicon.ico|robots.txt).*)",
    ],
};
```

**Behavior:** Unauthenticated requests to protected routes receive a 302 redirect to `/login`.

**Note:** The middleware only checks cookie presence, not JWT validity. Full JWT validation happens on the FastAPI side when API calls are made. This is intentional — the middleware is a UX optimization to redirect unauthenticated users quickly, not a security boundary.

### 8.7 Updated Onboarding Gate

The existing `OnboardingGate` component (REQ-012 §3.3) gains a new layer:

**Current flow:** Persona check → onboarding or dashboard
**New flow:** Auth check (middleware) → Persona check (OnboardingGate) → onboarding or dashboard

The OnboardingGate component itself does not change — it still checks persona status via `usePersonaStatus()`. The auth layer is handled upstream by Next.js middleware.

### 8.8 API Client Updates

The existing API client (`frontend/src/lib/api-client.ts`) needs two changes:

1. **Add `credentials: 'include'`** to all fetch calls. This ensures the JWT cookie is sent with cross-origin requests (needed if backend and frontend are on different origins in production).

2. **Add 401 interceptor**: When any API call returns 401, redirect to `/login` and clear TanStack Query cache.

```typescript
// In api-client.ts fetch wrapper
if (response.status === 401) {
    queryClient.clear();
    window.location.href = "/login";
}
```

### 8.9 Logout

**Trigger:** "Sign Out" button in settings page or user menu.

**Flow:**
1. Call `POST /api/v1/auth/logout` (clears httpOnly cookie server-side)
2. Clear TanStack Query cache (`queryClient.clear()`)
3. Clear AuthProvider context
4. Redirect to `/login`

**"Sign out of all devices":**
1. Call `POST /api/v1/auth/change-password` or dedicated endpoint to set `token_invalidated_before = now()`
2. Then execute normal logout flow (steps 1-4 above)
3. Other devices' JWTs become invalid on their next API call (401 → redirect to /login)

---

## 9. Migration from Single-User Mode

### 9.1 Feature Flag

Authentication is gated behind `AUTH_ENABLED` (boolean environment variable). This allows:
- **Local development:** `AUTH_ENABLED=false` — existing behavior, `DEFAULT_USER_ID` from env
- **Hosted deployment:** `AUTH_ENABLED=true` — full auth flow

### 9.2 Data Migration

When transitioning from local mode to hosted mode:

1. The existing user row in `users` table remains
2. On first login (OAuth or magic link), FastAPI checks for existing user by email
3. If the existing user's email matches the OAuth/magic link email:
   - FastAPI links the account to the existing user
   - All existing data (personas, jobs, applications) is preserved
4. If emails don't match:
   - New user is created
   - Existing data remains attached to the original user (accessible by signing in with that email)

**No bulk data migration needed.** The `users.id` → `personas.user_id` FK chain handles isolation naturally.

### 9.3 Backward Compatibility

When `AUTH_ENABLED=false`:
- Auth endpoints (`/api/v1/auth/*`) are still mounted but unused by the frontend
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

FastAPI API endpoints are protected by the combination of:
- `SameSite=Lax` cookie attribute — prevents cross-site form POSTs
- CORS with `allow_credentials=True` + explicit `ALLOWED_ORIGINS` (not `*`) — prevents cross-origin JavaScript requests
- The browser's Same-Origin Policy blocks cross-origin `fetch()` with credentials unless the server's CORS policy explicitly allows the requesting origin

**CRITICAL:** `ALLOWED_ORIGINS` must never be set to `*` when `allow_credentials=True`. This would allow any website to make authenticated API calls on behalf of the user.

**OAuth endpoints** additionally validate the `state` parameter to prevent CSRF on OAuth callbacks.

### 10.3 Token Rotation

JWTs are not automatically rotated per-request (unlike Auth.js). Mitigation:
- 7-day `maxAge` limits exposure window
- `token_invalidated_before` provides explicit revocation
- **Future enhancement:** Implement refresh token rotation — short-lived access tokens (15 min) + database-backed refresh tokens for stronger revocation guarantees

### 10.4 OAuth Security

- **PKCE** (Proof Key for Code Exchange) is used for all OAuth flows
- **State parameter** validated to prevent CSRF on OAuth callbacks
- **Nonce** validated for OIDC providers (Google, LinkedIn)
- OAuth tokens (refresh_token, access_token) encrypted at rest in the `accounts` table

### 10.5 Magic Link Security

- Token expires in 10 minutes
- Single-use (deleted after verification)
- Token hashed before database storage (32-byte random tokens = 256 bits entropy)
- Rate-limited: Max 5 magic link requests per email per hour
- Also serves as the password reset mechanism — no separate reset token system needed

### 10.6 Token Revocation

JWT strategy means tokens cannot be individually revoked. Mitigations:

1. **Short maxAge (7 days)** — Limits the window if a token is stolen
2. **Invalidation timestamp** — `users.token_invalidated_before` column. "Sign out everywhere" sets this to `now()`. FastAPI checks `iat < token_invalidated_before` on every request and rejects stale JWTs.
3. **Future enhancement:** Switch to short-lived access tokens (15 min) + database-backed refresh tokens for stronger revocation guarantees.

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

**Rate limiting on auth endpoints:**

| Endpoint | Limit | Key |
|----------|-------|-----|
| `POST /auth/verify-password` | 5 per 15 minutes | Per email address |
| `POST /auth/register` | 3 per hour | Per IP address |
| `POST /auth/change-password` | 5 per hour | Per authenticated user |
| `POST /auth/magic-link` | 5 per hour | Per email address |
| `GET /auth/providers/{provider}` | 10 per hour | Per IP address |

**User enumeration prevention:** The `verify-password` endpoint always performs a bcrypt comparison (using a dummy hash on miss) to maintain constant-time response regardless of whether the email exists. The `register` endpoint returns `409 Conflict` for existing emails — this is an acceptable trade-off (email enumeration via registration is a known limitation; mitigated by rate limiting). The `magic-link` endpoint always returns success regardless of whether the email exists.

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

# Auth
AUTH_ENABLED=true                        # Toggle auth mode
AUTH_SECRET=<random-32-byte-hex>         # JWT signing secret

# OAuth Providers
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=

# Email
EMAIL_FROM=noreply@zentropyscout.com
RESEND_API_KEY=

# Frontend URL (for OAuth redirect after callback)
FRONTEND_URL=http://localhost:3000
```

### Frontend (`frontend/.env`)

```bash
# Existing (unchanged)
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# No auth-specific frontend env vars needed.
# All auth is handled by FastAPI — the frontend just calls API endpoints
# and the JWT cookie is set by FastAPI responses.
```

**Note:** Unlike Auth.js which requires `AUTH_SECRET` and `AUTH_URL` on the frontend, the custom approach requires NO auth secrets on the frontend. The JWT cookie is httpOnly — the frontend cannot read it. All auth logic lives in FastAPI.

---

## 12. Open Questions

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | Which email provider for magic links? | Recommended: Resend | See §3.3. Simple REST API via `httpx`. Swappable. |
| 2 | Session duration (maxAge)? | Proposed: 7 days | Reduced from 30 days to limit stolen token exposure. |
| 3 | Should we support "Sign out of all devices"? | Included (v0.1) | Implemented via `users.token_invalidated_before` column. See §10.6. |
| 4 | Custom email template for magic links? | Deferred | Use plain-text initially. Add branded template when design system is ready. |
| 5 | Should LinkedIn OAuth use basic profile or full profile scope? | Proposed: basic (openid, email, profile) | Full profile requires LinkedIn partner review. Basic is self-serve. |
| 6 | Domain for production (affects OAuth redirect URLs)? | TBD | Needed before registering OAuth apps with Google/LinkedIn. |
| 7 | OAuth library? | Recommended: `httpx-oauth` | Async OAuth2 client library. Reduces per-provider code from ~80 to ~30 lines. Or implement manually with `httpx` for full control. |

---

## 13. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-18 | v0.1 | Initial draft — 3 providers, JWT-in-cookie, account linking |
| 2026-02-18 | v0.2 | Security hardening — JWT revocation (`token_invalidated_before`), `aud`/`iss` claims, pre-hijack defense, CSRF for FastAPI, audit logging, reduced maxAge to 7 days, rate limit key fix, adapter UUID note, connection pool note |
| 2026-02-18 | v0.3 | Added @auth/pg-adapter research spike note to §8.1 — UUID PKs, snake_case columns, custom columns compatibility must be verified before implementation |
| 2026-02-18 | v0.4 | Added email+password as fourth identity provider (§4.3). Added register page (§8.3), account settings section (§8.3a), password endpoints (§7.5), password security (§10.8). Magic link now dual-role: standalone sign-in + password reset. Updated login page with email/password form. Updated scope, design decisions (§3.4), edge cases, users table (password_hash), Auth.js config (Credentials provider), middleware matcher, audit logging. |
| 2026-02-19 | v0.5 | **Major revision: Custom FastAPI-owned auth.** Replaced Auth.js v5 with custom implementation per Decision 001. FastAPI now issues and validates JWTs. All OAuth flows handled by FastAPI. Frontend has no auth library dependency. Removed all `next-auth`, `@auth/pg-adapter` references. Added OAuth endpoints (§7.5), magic link endpoints, `/auth/me` endpoint. Rewrote §8 (frontend integration) for custom `SessionProvider` and `useSession()` hook. Cookie renamed from `authjs.session-token` to `zentropy.session-token`. Simplified frontend env vars (no auth secrets needed on frontend). Added OAuth initiation + callback endpoint specs. Updated security considerations for custom CSRF + token rotation approach. |
