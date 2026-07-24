# CHIMERA Studio — Persistence Architecture

Assignment 008: Filesystem persistence and user-scoped ownership isolation.

---

## Overview

CHIMERA Studio stores all interview sessions, forged cartridges, draft
artifacts, and version history on the local filesystem.  Every persisted
entity is scoped to an authenticated user account.  No in-memory-only
data structures survive process restarts — all state is round-tripped
through JSON files.

The persistence layer is stateless at the service level: repositories
accept an `owner_user_id` parameter on every call rather than binding
a user at construction time.  This keeps services reusable across
requests within the same process.

---

## Identity Provider Contract

CHIMERA does not perform authentication.  It delegates identity
resolution to a pluggable `IdentityProvider` implementation supplied
at startup.

### Protocol

```python
class IdentityProvider(Protocol):
    async def resolve(self, request: Request) -> UserContext: ...
```

The provider receives the raw Starlette `Request` and must return a
trusted `UserContext` on success, or raise an exception on failure.
CHIMERA catches all exceptions from the provider and returns a generic
401 response without revealing the failure reason.

### UserContext

```python
@dataclass(frozen=True)
class UserContext:
    user_id: str          # unique, immutable user identifier
    account_id: str | None = None
    roles: tuple[str, ...] = ()
```

CHIMERA reads only `user_id` for ownership scoping.  `account_id` and
`roles` are reserved for future use by ARCHEngine-backed providers.

### DevIdentityProvider (default)

The default provider verifies HMAC-SHA256 signed handshakes passed in
the `X-Identity-Handshake` HTTP header.  It is suitable for development,
testing, and the current Render deployment.

Production deployments **must** set the `CHIMERA_IDENTITY_SECRET`
environment variable.  The provider refuses to start in production
mode without it.

---

## Signed Handshake Flow

```
┌──────────────┐                          ┌────────────────┐
│  Identity     │  sign_handshake(secret,  │  CHIMERA       │
│  Provider     │  user_id)                │  Studio        │
│  (external)   │─────────────────────────>│                │
│               │                          │  DevIdentity   │
│               │  returns IdentityHandshake│  Provider      │
│               │<─────────────────────────│                │
│               │                          │                │
│               │  HTTP request with       │                │
│               │  X-Identity-Handshake    │                │
│               │─────────────────────────>│                │
│               │                          │  1. Decode     │
│               │                          │  2. Verify HMAC│
│               │                          │  3. Check exp  │
│               │                          │  4. Nonce check│
│               │                          │  5. UserContext │
└──────────────┘                          └────────────────┘
```

### IdentityHandshake

```python
@dataclass(frozen=True)
class IdentityHandshake:
    user_id: str
    issued_at: datetime
    expires_at: datetime
    nonce: str
    environment: str     # "dev" | "staging" | "production"
    signature: str       # HMAC-SHA256 over all other fields
```

### Signing

1. Construct an unsigned `IdentityHandshake` with a fresh nonce
   (`secrets.token_urlsafe(16)`) and expiry (`now + ttl_seconds`).
2. Canonicalize all fields except `signature` to deterministic JSON.
3. Compute HMAC-SHA256(shared_secret, canonical_bytes).
4. Encode the digest as base64url.

### Verification

1. Decode the header token from base64url to JSON.
2. Reconstruct `IdentityHandshake.from_dict()`.
3. Recompute the HMAC and compare with `hmac.compare_digest()`.
4. Check `expires_at > now`.
5. Check the nonce has not been used (replay protection).

### Transport Encoding

The full `IdentityHandshake` dict is serialized to JSON, then
base64url-encoded for HTTP header transport:

```
token = base64url(json(handshake.to_dict()))
```

### Nonce Store

The `_NonceStore` provides replay protection with:

- **TTL**: Nonces expire after 300 seconds (configurable).
- **Bounded size**: Maximum 10,000 entries.
- **Eviction**: Oldest entry removed when the store is full.
- **Cleanup**: Expired entries are lazily pruned on each access.

Note: The nonce store is in-memory.  After a process restart, previously
used nonces are forgotten.  This is acceptable because handshakes also
have a short TTL (default 1 hour) and the nonce store only needs to
prevent replay within a single process lifetime.

---

## Ownership Model

Every repository and service method that touches persisted data accepts
an `owner_user_id` parameter.  There is no session-level or
constructor-level user binding.

```
SessionRepository.save(session, owner_user_id)
SessionRepository.load(session_id, owner_user_id)
CartridgeService.create(draft, owner_user_id)
CartridgeService.get(identifier, owner_user_id)
```

### Isolation Rules

1. **Sessions**: A user can only load, modify, or forge sessions they
   own.  Cross-user session access returns HTTP 404 (not 403), to
   prevent user enumeration.

2. **Cartridges**: A user can only inspect, export, validate, or view
   version history for cartridges they own.  Cross-user cartridge access
   returns HTTP 404.

3. **Clone**: Cloning a cartridge preserves the owner.  The clone is
   created under the cloning user's ownership namespace.

4. **Dashboard**: The cartridge list endpoint returns only cartridges
   owned by the authenticated user.

### Non-Disclosing Responses

All ownership violations return 404 ("not found") rather than 403
("forbidden").  This prevents an attacker from determining whether a
resource exists under another user's ownership.

---

## Filesystem Layout

```
data/
  sessions/
    {owner_user_id}/
      {session_id}.json
  cartridges/
    {owner_user_id}/
      {identifier}.json           # current version
      _uuid_index.json            # UUID → identifier mapping
      {identifier}/
        versions/
          {cartridge_id}.json     # historical versions
```

### Session Storage

Each session is serialized using `InterviewEngine.serialize_session()`,
which produces a JSON dict containing session state, answers, draft
fields, timestamps, and the interview progress.

### Cartridge Storage

Each cartridge is stored as a `_CartridgeRecord` containing:

- `cartridge`: The full `PersonaCartridge` dict (via `to_dict()`).
- `lifecycle`: Metadata including state, timestamps, export count,
  source session ID, tags, and notes.

The `_uuid_index.json` maps manifest UUIDs to persona identifiers for
快速 UUID-based lookups without scanning all files.

### Version History

When a cartridge is re-forged or cloned, the previous version is saved
to the `versions/` subdirectory.  Each version file is named by its
cartridge UUID and contains the full record at that point in time.

---

## Path-Safety Rules

`FilesystemStorage` validates all domain and key arguments to prevent
path traversal and cross-directory access:

| Rule | Description |
|------|-------------|
| **Component validation** | Only `[a-zA-Z0-9_-]` characters are allowed in path components. |
| **No `..`** | Double-dot sequences are rejected. |
| **No separators** | Forward slash and backslash are rejected in key arguments (allowed in domain for nesting). |
| **Prefix check** | Resolved absolute paths are checked to ensure they remain within the storage root. |
| **Atomic writes** | All writes use a `.tmp` file + `shutil.move()` for atomicity. |

### Validation Functions

- `_validate_component(value)`: Validates a single path component.
- `_validate_domain(domain)`: Validates a domain path (may contain `/`).
- `_validate_key(key)`: Validates a storage key (single component).
- `_safe_path(domain, key)`: Resolves and validates the full path.
- `_safe_domain_path(domain)`: Resolves and validates a domain directory.

---

## Restart Behavior

All state survives process restarts because:

1. **Sessions** are persisted to disk after every answer submission,
   skip, forge, complete, or cancel operation.

2. **Cartridges** are persisted to disk immediately after forging,
   cloning, archiving, restoring, or metadata updates.

3. **Version history** is appended to disk on every forge or clone.

4. **UUID index** is rewritten on every cartridge save.

On restart:

- `FilesystemStorage` re-reads from the `data/` directory.
- Repositories rehydrate from disk on first access (lazy loading with
  in-memory caching).
- In-memory caches (session cache, cartridge cache, UUID index cache)
  are cold and repopulated on demand.
- The nonce store is empty (acceptable — handshakes have short TTLs).

### Cache Clear

`SessionRepository.clear_cache()` and `CartridgeRepository.clear_cache()`
discard the in-memory cache without affecting disk.  Subsequent reads
rehydrate from disk.  This is used to verify persistence correctness
in tests.

---

## Failure Handling

| Scenario | Behavior |
|----------|----------|
| Missing identity header | 401 "Authentication required" |
| Invalid handshake token | 401 "Invalid identity handshake" |
| Expired handshake | 401 "Identity handshake expired" |
| Reused nonce | 401 "Identity handshake expired" |
| Missing `CHIMERA_IDENTITY_SECRET` in production | RuntimeError at startup |
| Path traversal attempt | ValueError raised, 500 response |
| Session not found | 404 "Session not found" |
| Cartridge not found | 404 "Cartridge not found" |
| Incomplete interview at forge | 409 "INTERVIEW_INCOMPLETE" |
| Filesystem write failure | Exception propagates, 500 response |

The identity middleware catches all exceptions from the provider and
returns a generic 401 JSON response:

```json
{"error": "UNAUTHORIZED", "message": "Authentication required"}
```

This prevents information leakage about why authentication failed.

---

## ARCHEngine / CHIMERA Responsibility Boundary

### ARCHEngine Responsibilities

- **Authentication**: ARCHEngine authenticates users via its own
  identity system (e.g., OAuth, session cookies, API keys).
- **Identity bridging**: ARCHEngine creates signed handshakes for
  authenticated users and passes them to CHIMERA via the
  `X-Identity-Handshake` header.
- **Secret management**: ARCHEngine sets the `CHIMERA_IDENTITY_SECRET`
  environment variable with a shared secret.
- **Deployment**: ARCHEngine manages the Render deployment, environment
  variables, and process lifecycle.

### CHIMERA Responsibilities

- **Identity verification**: CHIMERA verifies the signed handshake and
  extracts the `UserContext`.
- **Ownership enforcement**: All data access is scoped to the verified
  `user_id`.
- **Persistence**: CHIMERA manages the filesystem storage, repositories,
  and service layer.
- **Interview lifecycle**: CHIMERA owns the interview engine, question
  flow, draft management, and cartridge forging.
- **API and UI**: CHIMERA serves the Studio UI and REST API.

### Integration Point

ARCHEngine mounts CHIMERA as a sub-application at `/chimera`.  The mount
configures:

1. The `DevIdentityProvider` with the shared HMAC secret.
2. The `IdentityMiddleware` for request-scoped identity resolution.
3. The persistence layer with filesystem-backed repositories.
4. Template and static file paths adjusted for the `/chimera` prefix.

CHIMERA's web routes (non-`/api/`) and exempt API routes (`/api/health`,
`/api/schema`, `/api/validate`, `/api/forge`) pass through without
identity resolution.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CHIMERA_ENV` | No | `"development"` | Runtime environment (`development`, `staging`, `production`). |
| `CHIMERA_IDENTITY_SECRET` | Yes (production) | `"chimera-dev-secret"` (dev only) | HMAC-SHA256 shared secret for handshake signing/verification. |

### Data Directory

The `DATA_DIR` constant resolves to `{CHIMERA_ROOT}/data` by default.
When mounted inside ARCHEngine, this becomes
`{ARCHEngine}/backend/chimera_app/data`.
