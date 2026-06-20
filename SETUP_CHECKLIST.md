# 本地环境搭建检查清单

> 方案：Chat 用 DeepSeek API + Embedding 用本地 BGE 模型 + Reranker 用本地 Qwen3 模型

---

## 安装项

- [ ] **Python 3.12+**
- [ ] **Node.js 16+** + **pnpm**
- [ ] **uv**（Python 包管理器，推荐 0.11.9+）
- [ ] **Docker Desktop**（用于 MySQL / Redis / Milvus 基础设施）
- [ ] **Ollama**（可选，仅当 `LLM_TYPE=OLLAMA` 时需要，端口 11434）

## API Key

- [ ] **DeepSeek API Key** — 去 [platform.deepseek.com](https://platform.deepseek.com) 申请（当前 `LLM_TYPE=DEEPSEEK`）

## 模型下载（自动）

以下模型首次使用时会自动从 HuggingFace 镜像下载，无需手动操作：

| 模型 | 用途 | 大小 |
|------|------|------|
| `BAAI/bge-large-zh` | 文本嵌入 | ~1.3 GB |
| `BAAI/bge-reranker-large` | 文档重排序 | ~1.1 GB |
| `openai/clip-vit-base-patch32` | 图片嵌入 | ~600 MB |

> 已设置 `HF_ENDPOINT=https://hf-mirror.com` 镜像加速。

另外 `backend/.env` 中 `RERANKER_MODEL_PATH` 指向本机已下载的 `Qwen/Qwen3-Reranker-0.6B`，如需使用 bge-reranker 改为空值即可。

## 配置文件

- [ ] `backend/.env` — `LLM_TYPE=DEEPSEEK`，填好 API Key
- [ ] `DjangoUserService/.env` — 填好 JWT

其余项（数据库、Redis、Milvus 地址）默认 `localhost`，无需修改。

## 启动（按顺序）

### 1. 基础设施（Docker）

```bash
docker compose up -d
```

启动 MySQL `:3306`、Redis `:6379`、Milvus `:19530`（含 etcd + MinIO）。

### 2. 数据库初始化

```bash
docker compose exec mysql mysql -uroot -p123 -e "CREATE DATABASE IF NOT EXISTS user_service CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
cd DjangoUserService && uv sync && uv run python manage.py migrate
```

### 3. Django 用户服务（端口 8001）

```bash
cd DjangoUserService && uv run python manage.py runserver 8001
```

### 4. FastAPI 后端（端口 8000）

```bash
cd backend && uv sync && uv run uvicorn main:app --reload --port 8000
```

首次启动会自动建表，并下载 BGE Embedding 模型（需要几分钟）。

### 5. 前端（端口 5173）

```bash
cd front && pnpm install && pnpm dev
```

### 6. 验证

打开 `http://localhost:5173`，注册/登录后可以使用 AI 问答和知识库功能。

---

## 停止

```bash
docker compose down    # 停止基础设施（数据不丢失）
docker compose down -v # 同时删除数据卷
```

## 常见问题

- **MySQL 端口冲突**：本机已有 MySQL → 修改根 `.env` 中 `MYSQL_PORT` 为其他端口（如 3307），同时更新 `backend/.env` 和 `DjangoUserService/.env` 中的端口
- **Embedding 模型下载慢**：已配置 `HF_ENDPOINT` 镜像，首次需几分钟
- **Milvus 启动失败**：Mac 上需确保 Docker Desktop 已授予足够内存（建议 > 4GB）
