# AI Agent 全栈应用

Vue 前端 + FastAPI 后端 + LangChain / DeepSeek Agent + PostgreSQL / pgvector。
支持注册登录、聊天、历史记录、UTF-8 文本上传和 RAG 检索。

## 项目结构

```text
项目/
├─ backend/                  # 后端源代码及 Python 依赖
│  ├─ server.py              # FastAPI 接口入口
│  ├─ agent_langchain.py     # DeepSeek Agent 与时间工具
│  ├─ rag.py                 # 智谱 embedding、文档切块与检索
│  ├─ db.py                  # 用户、会话及聊天记录读写
│  └─ requirements.txt
├─ frontend/                 # Vue / Vite 前端
├─ database/
│  └─ schema.sql             # 数据库初始化脚本
├─ deploy/                   # Dockerfile 与 Nginx 配置
├─ samples/                  # 可上传测试的示例文本
├─ logs/                     # 本地运行日志（不提交 Git）
├─ archives/                 # Docker 镜像归档（不提交 Git）
├─ docker-compose.yml        # 数据库、后端、前端的编排入口
├─ .env                      # 本地配置（不提交 Git）
├─ .env.example              # 配置模板
└─ README.md
```

`.venv`、`.venv2`、`node_modules`、`dist` 和 Python 缓存属于本地环境或生成文件。
现有虚拟环境保留；下面的命令以 `.venv` 为例，也可使用已安装依赖的 `.venv2`。

## 配置

以下命令除前端启动外，都在项目根目录执行。
首次配置时复制模板；已有 `.env` 时直接编辑，避免覆盖已有配置。

```powershell
Copy-Item .env.example .env
```

填写 `DEEPSEEK_API_KEY`、`ZHIPU_API_KEY` 和数据库连接参数。
后端按源文件位置读取项目根目录的 `.env`，外部环境变量优先。

## 本地开发

### 1. Python 环境

如果还没有虚拟环境，先创建：

```powershell
python -m venv .venv
```

安装后端依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

### 2. 数据库

```powershell
docker compose up -d db
```

首次创建数据库时，Compose 会挂载 `database/schema.sql` 并自动初始化。
已有数据卷不会重新执行初始化脚本；现有数据库的表结构变更需要另外处理。

### 3. 后端

```powershell
.\.venv\Scripts\python.exe -m uvicorn server:app --app-dir backend --reload
```

接口文档：<http://127.0.0.1:8000/docs>。
`--app-dir backend` 让 Python 能找到 `server.py` 及它引用的同目录模块。

也可以单独运行终端 Agent：

```powershell
.\.venv\Scripts\python.exe backend/agent_langchain.py
```

### 4. 前端

在另一个终端执行：

```powershell
cd frontend
npm ci
npm run dev
```

打开终端显示的地址，通常为 <http://localhost:5173>。
Vite 将 API 请求代理到本机的 8000 端口。前端构建命令为 `npm run build`。
可用 `samples/rag_test_雾灯计划.txt` 测试文本上传和知识检索。

## Docker 启动整个应用

在项目根目录执行：

```powershell
docker compose up -d --build
```

网页入口为 <http://localhost>。容器中的 Nginx 将 API 请求转发给后端。
两个 Dockerfile 都以项目根目录为构建上下文，无需切换到 `deploy/`。

```powershell
docker compose logs -f backend
docker compose down
```

`docker compose down` 保留数据库数据卷。不要为了整理文件删除数据卷。
`archives/pgvector-pg16.tar` 是保留的本地镜像归档，日常启动不需要复制进镜像。
`logs/backend.log` 是整理前保留的日志；Docker 日志通过上面的 Compose 命令查看。
