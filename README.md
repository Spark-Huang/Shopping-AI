# Shopping AI

Shopping AI is a bilingual shopping assistant that combines product search, cart state, conversational memory, and layered safety checks. The repository contains the orchestrator API, search and memory services, safety service, web UI, deployment configuration, and offline tests.

## Services

- **orchestrator** — coordinates routing, retrieval, cart operations, conversation, and timing.
- **search** — embeds and queries the neutral product catalog with Milvus.
- **memory** — persists messages, user context, cart items, and orders in SQLite; optionally builds long-term memory with cognee and Milvus.
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

## Long-Term Memory

Every completed turn is stored in the SQLite `messages` table as a `user` and an `assistant` row. The orchestrator then asks the memory service to schedule cognee extraction asynchronously, so chat latency is not affected by embedding or knowledge-graph work. At the start of the next turn, cognee retrieves relevant chunks scoped to the `shopping_ai_memory` dataset, and those facts are appended to the existing `users.context` value. The context field remains unchanged as a compatibility and fallback path.

Cognee uses the same Milvus instance as product search but a separate dataset/collection name, preventing memory and catalog records from mixing. The `COGNEE_LLM_PROVIDER`, `COGNEE_EMBEDDING_PROVIDER`, and `COGNEE_EMBEDDING_DIMENSIONS` variables tune its model configuration; endpoint, model, and key values default to the shared gateway settings. If cognee, the LLM gateway, embedding endpoint, or Milvus is unavailable, the service logs a warning and keeps operating from SQLite. Set `MEMORY_EMBEDDING_ENABLED=false` to disable extraction and retrieval without changing the message persistence path.

## 长期记忆

每轮完整对话会以一条 `user` 消息和一条 `assistant` 消息写入 SQLite 的 `messages` 表。随后 orchestrator 调用 memory 服务异步触发 cognee 抽取，主聊天路径不会被 embedding 或知识图谱处理阻塞。下一轮开始时，cognee 会从 `shopping_ai_memory` 数据集中检索相关片段，并把结果追加到现有 `users.context`。`users.context` 保持原样，作为兼容和降级路径。

Cognee 与商品搜索共用同一个 Milvus 实例，但使用独立 dataset/collection 命名，避免记忆数据与商品索引混淆。可通过 `COGNEE_LLM_PROVIDER`、`COGNEE_EMBEDDING_PROVIDER` 和 `COGNEE_EMBEDDING_DIMENSIONS` 调整模型配置；端点、模型和密钥默认复用共享网关配置。若 cognee、LLM 网关、embedding 服务或 Milvus 不可用，服务会记录告警并继续使用 SQLite。设置 `MEMORY_EMBEDDING_ENABLED=false` 可关闭抽取与检索，但消息仍会持久化。
