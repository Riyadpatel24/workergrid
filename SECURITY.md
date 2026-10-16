# WorkerGrid + Project Friction Security Architecture

## Security Overview

WorkerGrid and Project Friction implement strict server-side multi-tenant data isolation, cryptographic token protection, IDOR prevention, and secure OAuth session management.

---

## Core Security Controls

### 1. Multi-Tenant Data Isolation
- **Server-Side Ownership Enforcement**: `user_id` is derived exclusively from validated JWT access tokens / HttpOnly session cookies via FastAPI's `get_current_user` dependency.
- **Body Payload Override Protection**: Client-supplied `user_id` parameters in HTTP request bodies are ignored or rejected.
- **Read / Write Isolation**: Database queries enforce `filter(Resource.user_id == current_user.id)` on all reads, updates, and deletions.

### 2. Insecure Direct Object Reference (IDOR) Protection
- **Existence Enumeration Prevention**: Requests targeting resources owned by another user return **HTTP 404 Not Found** (rather than 403 Forbidden) to prevent resource existence scanning.
- **Tenant-Scoped Uniqueness**: Repository unique constraints are scoped to `(user_id, full_name)` in PostgreSQL, preventing cross-tenant repository reservation attacks.

### 3. Token Encryption & Credential Safety
- **Symmetric Encryption at Rest**: GitHub OAuth tokens are encrypted prior to database insertion using Fernet symmetric encryption using AES-128-CBC with HMAC authentication via `encrypt_token()`.
- **Zero Token Leakage in Payloads**: Plaintext GitHub tokens are **never** placed into task payloads stored in PostgreSQL or Redis.
- **In-Memory Worker Decryption**: Workers fetch `UserGitHubAccount` from PostgreSQL using `user_id` and decrypt the token in worker memory via `decrypt_token()`.
- **API Masking**: Tokens are excluded from all REST API responses and logging output.

### 4. GitHub OAuth 2.0 & CSRF Protection
- **Cryptographic State Parameter**: `create_oauth_state` generates JWT-signed state tokens embedding a 10-minute expiration, `user_id`, and random 8-byte nonce.
- **CSRF State Verification**: `verify_oauth_state` checks signature integrity and expiration during callback handling.

### 5. Authentication & Cookie Security
- **JWT Signing**: Access tokens (30-min expiry) and Refresh tokens (7-day expiry) are signed using `HS256` with `SECRET_KEY`.
- **HttpOnly Cookies**: Session tokens are transmitted via `HttpOnly`, `SameSite=Lax` cookies with `secure=True` in production, preventing XSS access.
- **Password Hashing**: User passwords are hashed using Bcrypt with salt (`get_password_hash`). Plaintext passwords and hashes are never exposed in user responses.

---

## Security Audit Checklist

| Security Control | Implementation | Verification Status |
| :--- | :--- | :--- |
| **Token Safety in Tasks** | `project_friction/workflows/builder.py` | **VERIFIED (No plaintext tokens)** |
| **Multi-Tenant Read Isolation** | `app/api/friction_router.py`, `main.py` | **VERIFIED (Scoped to current_user.id)** |
| **IDOR Blocking (404)** | All endpoint handlers | **VERIFIED (Returns 404 Not Found)** |
| **OAuth CSRF Validation** | `app/core/security.py` | **VERIFIED (JWT signed + 10m expiry)** |
| **Password Hashing** | Bcrypt with salt | **VERIFIED** |
| **HttpOnly Cookies** | `set_auth_cookies()` | **VERIFIED** |
| **CORS Policy** | Restricted `ALLOWED_ORIGINS` | **VERIFIED** |
