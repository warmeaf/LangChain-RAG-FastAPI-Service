# 本地环境搭建检查清单

> 方案：Chat 用 DeepSeek API + Embedding 用本地 Ollama

## 安装项

- [ ] **Python 3.12+**
- [ ] **Node.js 16+**
- [ ] **uv**（Python 包管理器，推荐 0.11.9+）
- [ ] **MySQL**（端口 3306）
- [ ] **Redis**（端口 6379）
- [ ] **Ollama**（端口 11434，Embedding 模型用）
- [ ] **npm 或 pnpm**（前端依赖）

## API Key

- [ ] **DeepSeek API Key** — 去 [platform.deepseek.com](https://platform.deepseek.com) 申请

## 模型拉取（Ollama）

- [ ] `ollama pull qwen3-embedding:0.6b`（嵌入模型，**必须**）

## 模型下载（本地文件）

- [ ] **Qwen3-Reranker-0.6B** — 从 Hugging Face / ModelScope 下载到本地，记住路径

## 配置文件

- [ ] `backend/.env` — `LLM_TYPE=DEEPSEEK`，填好 API Key、数据库、Redis、JWT、重排序模型路径
- [ ] `DjangoUserService/.env` — 填好 JWT、数据库、Redis、Celery 配置
- [ ] `backend/app/config/chroma.yaml` — 向量数据库参数（一般默认即可）

## 数据库初始化

- [ ] MySQL 建库 `chat_history`（后端用）
- [ ] MySQL 建库 `user_service`（Django 用户服务用）
- [ ] `cd DjangoUserService && python manage.py migrate`（建表）

## 依赖安装

- [ ] `cd backend && uv sync`
- [ ] `cd front && npm install`（或 `pnpm install`）
- [ ] `cd DjangoUserService && uv sync`

## 启动验证（按顺序）

1. [ ] MySQL 启动
2. [ ] Redis 启动
3. [ ] Ollama 启动
4. [ ] Django 用户服务 — `cd DjangoUserService && python manage.py runserver 8001`
5. [ ] FastAPI 后端 — `cd backend && uvicorn main:app --reload`
6. [ ] Vue 前端 — `cd front && npm run dev`
