# Changelog

## [Unreleased]

### Added

- User registration, login, and authentication:
  - memory: `/auth/register`, `/auth/login`, `/auth/me` endpoints (bcrypt password hashing + JWT issuance).
  - orchestrator: `/auth/*` reverse proxy plus JWT enforcement on `/query/*`, `/cart/*`, `/orders/*`, and `/context/*`.
  - web: login/register page, token persistence, auth headers on API and SSE requests, account page with logout.
- `JWT_SECRET` environment variable in `.env.example` and compose.

### Fixed

- orchestrator config loader now opens YAML with `encoding="utf-8"` so non-ASCII configs load correctly on Windows.
- compose `milvus` service now exposes ports `19530`/`9091` so a locally run `search` can reach Milvus.

### Changed

- `docs/deployment-guide.md`: document `JWT_SECRET` setup and add a 401 troubleshooting note.

## 0.1.0 - 2026-08-28

### Added

- Initial orchestrator, search, memory, safety, and web application structure.
- Neutral bilingual shopping chat experience with product search, cart, order history, and context persistence.
- Milvus-backed catalog retrieval and neutral starter catalog data.
- Compose deployment with an nginx reverse proxy.
- Local development and test runner scripts.
- Offline unit tests and continuous integration workflow.
