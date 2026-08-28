# Shopping AI 贡献指南

欢迎参与 Shopping AI 开发！本指南帮助贡献者快速搭建环境并参与开发。

## 项目结构

```
Shopping-AI/
├── orchestrator/   # 编排服务（FastAPI+LangGraph）：意图路由→检索→购物车→对话生成
│   └── app/agents/ # planner / cartops / chatter / summarizer
├── search/         # 向量检索服务（Milvus + embeddings）
├── memory/         # 用户上下文/购物车/订单存储（SQLite）
├── safety/         # 内容安全护栏（基于 nemoguardrails 框架）
├── web/            # React 前端（Vite + TS + MUI）
├── platform/       # 共享配置（各服务 config.yaml）+ 商品数据 CSV
├── tools/          # devRunner（本地起服务）/ testRunner（跑测试）
├── tests/          # unit / integration
└── ops/            # docker-compose + nginx
```

**服务端口**：web 5173 / orchestrator 8009 / search 8010 / memory 8011 / safety 8012

## 环境要求

- Python 3.12.x，Node.js 22 LTS（npm 10.x）
- Docker + Docker Compose（跑 Milvus 全栈时需要）

## 快速开始

```bash
git clone https://github.com/Spark-Huang/Shopping-AI.git && cd Shopping-AI

# Python 侧
python3 -m venv .venv && source .venv/bin/activate
pip install -r orchestrator/requirements.txt -r search/requirements.txt \
            -r memory/requirements.txt -r safety/requirements.txt
pip install pytest httpx "httpx[socks]"

# Web 侧
cd web && npm install

# 环境变量
cp .env.example .env   # 填入你的网关地址/API key/模型名；.env 永不提交
```

## 日常开发

### 起服务

```bash
python tools/devRunner.py start    # 起全部服务（浏览器打开 5173）
python tools/devRunner.py status
python tools/devRunner.py stop
```

手动起单个服务（调试）：

```bash
cd orchestrator
PYTHONPATH=$(dirname $PWD) SHARED_CONFIG_ROOT=$PWD/../platform/configs \
  SAFETY_BASE_URL=http://127.0.0.1:8012 MEMORY_BASE_URL=http://127.0.0.1:8011 \
  SEARCH_BASE_URL=http://127.0.0.1:8010 \
  uvicorn app.main:app --port 8009
```

注：search 服务需要 Milvus（`docker compose -f ops/compose.yaml up milvus`，或跳过 search 做无检索开发）。

### 跑测试（提交前必过）

```bash
python -m pytest tests/unit -q          # Python 全量
cd web && npx tsc --noEmit && npx vitest run && npm run build
```

### 提交规范

```bash
git checkout -b feat/your-feature
git commit -m "Add xxx" / "Fix xxx"   # 清晰描述做了什么
git push origin feat/your-feature      # 开 PR，不直接推 main
```

Commit message 请保持清晰专业（如 `Add cart quantity validation`）。

## 代码约定

### AI Coding 哲学：代码越碎，越适合 AI

本项目的核心工程信念：**把代码拆得越碎，越适合 AI coding**。现代 AI 编码工具按上下文计费和理解——文件越小、职责越单一，AI 需要读的上下文越少，**越省 token**，修改越精准，出错率越低。因此：

1. **文件保持小而专一**：业务文件 ≤200 行，util 30-80 行；超了按职责拆分成子模块（参考 `orchestrator/app/agents/` 的拆法：一个千行大文件拆成多个单一职责小文件）
2. **拆分优先于注释**：与其写长注释解释复杂文件，不如拆成命名清晰的小文件让代码自解释
3. **提交 AI 友好**：每个 PR 聚焦单一职责，AI review 和人类 review 都更高效

### 其他约定

4. **模块依赖无环**：跨服务只走 HTTP，不互相 import
5. **测试跟随**：拆/改模块时同步更新 `tests/unit/<服务>/` 下对应测试（测试文件同样拆碎）
6. **i18n**：web 用户可见文案进 `src/i18n/{en,zh}.json`，两语言同步
7. **无版权头**：源文件不放 SPDX/版权声明头（保持现状）

## 常见问题

1. **服务报 `/app/platform/...` 找不到** → 缺 `SHARED_CONFIG_ROOT` 环境变量，用 devRunner 即可
2. **httpx 报 socksio 缺失** → `pip install "httpx[socks]"`
3. **search 连不上 milvus:19530** → Docker 网络主机名；本地跑起 compose 的 milvus 或设 `MILVUS_HOST=127.0.0.1`
4. **`.env` 改了不生效** → 重启服务
5. **测试报 `ModuleNotFoundError`** → 设置 `PYTHONPATH=仓库根`

## 反馈渠道

- Bug/功能建议：开 [Issue](https://github.com/Spark-Huang/Shopping-AI/issues)
- 不确定改动是否合适：先开 draft PR 讨论
