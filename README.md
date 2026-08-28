# Shopping AI

Shopping AI is a bilingual shopping assistant that combines product search, cart state, conversational memory, and layered safety checks. The repository contains the orchestrator API, search and memory services, safety service, web UI, deployment configuration, and offline tests.

## Services

- **orchestrator** — coordinates routing, retrieval, cart operations, conversation, and timing.
- **search** — embeds and queries the neutral product catalog with Milvus.
- **memory** — persists user context, cart items, and orders in SQLite.
- **safety** — applies input and output checks through an OpenAI-compatible endpoint.
- **web** — provides the responsive React and TypeScript chat interface.

## Quick Start

1. Install Docker Engine with Compose support and Node.js 20+.
2. Copy `.env.example` to `.env` and set model, embedding, safety, and gateway values.
3. Validate and start the stack:

   ```bash
   docker compose -f ops/compose.yaml config
   docker compose -f ops/compose.yaml up --build
   ```

4. Open `http://localhost:3000`.

The catalog is `platform/data/products.csv`. It intentionally contains neutral, self-contained product records and local SVG references; no external demo catalog is required.

## Local Development

Install each service's Python requirements and the web dependencies, then use:

```bash
python3 tools/devRunner.py start
python3 tools/testRunner.py unit
python3 tools/devRunner.py stop
``+

The runner starts `search`, `memory`, `safety`, `orchestrator`, and `web` with service-local logs and PID files under `.local-run/`.

## Testing

```bash
python3 tools/testRunner.py unit
``+

Service tests cover configuration loading, routing, cart operations, catalog ingestion, persistence, safety endpoints, and API behavior. Integration checks use the running orchestrator health endpoint at port `8009`.

## Configuration

Base service configuration lives under `platform/configs/`. Environment variables in `.env` override neutral gateway placeholders without changing tracked YAML. See `.env.example` for the supported keys.
