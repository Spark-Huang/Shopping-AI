# 贵客来部署指南（本地开发方式）

面向需要改代码的贡献者：本地裸跑全部服务，改完即时生效。

## 前置条件

| 组件 | 版本 | 用途 |
|---|---|---|
| Docker | 20.x+ | 只跑 Milvus 向量库 |
| Python | 3.12.x | 后端服务 |
| Node.js | 22 LTS | 前端 |
| LLM 网关 | OpenAI 兼容 | chat + embedding 各一模型（vLLM/Ollama/聚合网关均可） |

## 步骤 1：克隆 + 依赖

```bash
git clone https://github.com/Spark-Huang/Shopping-AI.git && cd Shopping-AI
python3 -m venv .venv && source .venv/bin/activate
pip install -r orchestrator/requirements.txt -r search/requirements.txt \
            -r memory/requirements.txt -r safety/requirements.txt
pip install pytest httpx "httpx[socks]"
cd web && npm install && cd ..
```

## 步骤 2：环境变量

```bash
cp .env.example .env
# 编辑 .env：填你的网关地址/key/模型名（LLM_*/EMBED_*/SAFETY_*）
# 注册登录还需要 JWT_SECRET：设一段随机长字符串（memory 与 orchestrator 必须一致）
```

`.env` 永不提交。

## 步骤 3：起 Milvus（Docker）

```bash
docker compose -f ops/compose.yaml up -d milvus-etcd milvus-minio milvus-standalone
```

## 步骤 4：本地地址 override

仓库 `platform/configs/*/config.yaml` 默认是 Docker 网络主机名。裸跑需创建 override（已被 .gitignore，不会误提交）。

`platform/configs/search/config-local.yaml`：

```yaml
text_embed_port: "http://localhost:<网关端口>/v1"
text_model_name: "<embedding模型名>"
image_embed_port: "http://localhost:<网关端口>/v1"
image_model_name: ""
db_port: "http://localhost:19530"
data_path: "<仓库绝对路径>/platform/data/products.csv"
```

`platform/configs/orchestrator/config-local.yaml`：

```yaml
llm_port: "http://localhost:<网关端口>/v1"
retriever_port: "http://localhost:8010"
memory_base_url: "http://localhost:8011"
safety_base_url: "http://localhost:8012"
```

## 步骤 5：起服务

一键（推荐）：

```bash
python tools/devRunner.py start
```

或手动（每个终端一个，统一先 export）：

```bash
export PYTHONPATH=$PWD SHARED_CONFIG_ROOT=$PWD/platform/configs CONFIG_OVERRIDE=config-local.yaml
set -a; source .env; set +a
```

```bash
cd memory       && uvicorn app.main:app --port 8011
cd safety       && uvicorn app.main:app --port 8012
cd search       && uvicorn app.main:app --port 8010   # 首次自动入库商品数据，需几分钟
cd orchestrator && uvicorn app.main:app --port 8009
cd web && npm run dev                                  # http://localhost:5173
```

## 验证部署

```bash
curl http://localhost:8009/health   # 200
curl http://localhost:8010/health   # 200
curl http://localhost:8011/health   # 200
curl http://localhost:8012/health   # 200
```

浏览器开 http://localhost:5173，问“给我看150美元以下的夏季连衣裙”，收到带价格的商品推荐即成功。

## 常见问题

1. **连 `http://search:8010` / `milvus:19530` 失败** → 忘了 `CONFIG_OVERRIDE=config-local.yaml`
2. **localhost 调用超时** → 系统代理劫持：`export NO_PROXY=localhost,127.0.0.1 && unset ALL_PROXY all_proxy`
3. **milvus 连不上** → `docker ps | grep milvus` 确认三件套在跑
4. **httpx 报 socksio** → `pip install "httpx[socks]"`
5. **chat 报 Missing credentials** → `.env` 没配好或没 source
6. **改 .env 不生效** → 重启对应服务
7. **测试报 ModuleNotFoundError** → `export PYTHONPATH=仓库根`
8. **登录/注册返回 401 或 token 校验失败** → 确认 memory 与 orchestrator 读到同一个 `JWT_SECRET`；手动方式需 `set -a; source .env; set +a` 后再起两个服务（`devRunner.py start` 不自动加载 .env，未设置时会回退到默认开发密钥，仅限本地自测）

## 端口总览

web 5173 / orchestrator 8009 / search 8010 / memory 8011 / safety 8012 / Milvus 19530
