# 贵客来（Guikelai）

贵客来是一个只服务贵州特色购物的智能 Agent：用户说清送礼对象、预算与口味后，系统从贵州食品、黔茶、非遗手作和民族纺织品目录中检索、比较并生成可执行的购物清单。应用支持中文/英文对话、图片找相似、购物车、收藏、预算与购买记录。

> 参赛定位：赛道三「开放创新 / AI × 新消费」。当前目录包含 52 个真实存在的贵州商品品类；价格是人民币参考价，购买前须在跳转后的商家页面核对。项目不生成虚构商品或虚构用户评价。

## Services

- **orchestrator** — coordinates routing, retrieval, cart operations, conversation, and timing.
- **search** — embeds and queries the live external product catalog with Milvus.
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

### Live Product Data & Freshness

Product search starts from the indexed Milvus catalog and refreshes live Dangdang results on demand. Every crawled record carries `crawled_at`. A query reuses records within the configured TTL; once the TTL expires it attempts a crawl, embeds the new records, and returns them. If crawling or embedding fails, the existing Milvus results are returned with `stale: true` so the shopping flow is never blocked.

Set `DATA_FRESHNESS_HOURS` (default: `24`) for the deployment default. Users can change the value from **Me → Data freshness**; the setting takes precedence over the environment variable. `DATA_FRESHNESS_FILE` overrides the storage path for that setting.

### 商品数据与新鲜度

商品搜索基于 Milvus 中已索引的目录，并按需刷新 Dangdang 实时结果。每条爬取记录都带 `crawled_at`：TTL 内直接复用；超过 TTL 会尝试重爬、写入向量库后返回。若爬取或向量化失败，则返回现有数据并标记 `stale: true`，不阻塞主流程。

通过 `DATA_FRESHNESS_HOURS` 配置部署默认值（默认 24 小时）。用户可在 **我的 → 数据新鲜度** 中修改；该设置优先于环境变量。`DATA_FRESHNESS_FILE` 可覆盖设置存储路径。

商品目录位于 `platform/data/products.csv`，来源与合规说明见 `docs/catalog-sources.md`。本地图片是清晰标注的商品示意图，不代表具体商家 SKU。

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
