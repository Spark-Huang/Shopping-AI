# Contributing to 贵客来

Thanks for helping improve 贵客来, the Guizhou specialty shopping agent.

## Setup

```bash
git clone <repository-url>
cd Shopping-AI
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r orchestrator/requirements.txt -r search/requirements.txt -r memory/requirements.txt -r safety/requirements.txt
npm --prefix web install
```

## Development Workflow

1. Create a focused branch for one change.
2. Keep public API and configuration changes backward-compatible when practical.
3. Add or update tests for changed behavior.
4. Run `python3 tools/testRunner.py unit`.
5. Run `docker compose -f ops/compose.yaml config` when deployment files change.
6. Submit a concise pull request describing the behavior change and validation.

## Style

- Python: type hints where useful, explicit imports, and small testable functions.
- TypeScript/React: functional components, clear prop types, and localized user-facing strings.
- YAML: two-space indentation and neutral placeholders.
- Commit messages: imperative subject lines without issue numbers in the subject.

## Catalog Data

Product records in `platform/data/products.csv` must describe real Guizhou product categories, remain neutral and suitable for redistribution. Preserve the schema, keep image references local, cite authoritative category sources in `docs/catalog-sources.md`, label reference prices and illustrations honestly, and never add fabricated reviews or merchant claims.
