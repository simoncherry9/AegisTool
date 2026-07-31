# AegisWiFi — Tests state

## Current tests (backend/tests/)
- `conftest.py`: In-memory SQLite fixtures, TestClient, auto-reset engine singleton
- `test_health.py`: Health endpoint smoke test
- `test_scope.py`: Parser (valid, extra keys, bad band, invalid YAML) + PolicyEngine (in-scope, out-of-scope, unpermitted, expired, frame budget, GPU temp)
- `test_security.py`: Encryption/decryption roundtrip, redact function

## Test configuration
- `asyncio_mode = auto` (pytest-asyncio)
- `addopts = -q -ra`
- `testpaths = ["backend/tests"]`
- Mypy strict disabled for tests (`disallow_untyped_defs = false`)
- Ruff: `S101` (assert) and `PLC0415` (import) allowed in tests

## Missing tests
- No engagement API integration tests (create, list, update, activate, close, errors)
- No engagement service unit tests
- No migration tests
- No scope service integration tests (scope_import)
- No database model tests
- No CLI tests
- No integration tests against external tools
- No PCAP fixtures for handshake testing (§36)
- No lab environment configured