# AegisWiFi — Security internals (minuta §19, §34)

## Key management (core/security.py)
- Fernet symmetric encryption (cryptography library)
- Key auto-generated on first use, persisted to `paths.data_dir/.aegis_key`
- Can be pre-configured via `AEGISWIFI__SECURITY__ENCRYPTION_KEY_B64` env var or `settings.security.encryption_key_b64`
- Functions: `encrypt_secret(plaintext)` → Fernet token string; `decrypt_secret(token)` → plaintext; `redact(value, visible=4)` → masked display

## Config secrets
- `settings.security.secret_key`: auto-generated random for auth tokens (not yet used — require_auth defaults to False)
- `settings.security.require_auth`: auth enforcement toggle

## API security
- CORS locked to localhost:5173 origins by default
- docs/redoc disabled in production
- No auth middleware implemented yet (require_auth=False in tests)

## Process security
- No shell=True anywhere (AGENTS.md enforcement)
- `subprocess.run` with arg lists only
- Approved binaries allowlist (not yet implemented — pending adapter framework)