-- ============================================================
-- schema.sql —— PostgreSQL + pgvector 的建库建表脚本
-- ============================================================
--
-- 用途：
--   1) Docker 首次启动时自动执行（见 docker-compose.yml 的挂载）
--   2) 部署到 Linux 服务器时，也用同一份脚本
--
-- 注意：PostgreSQL 语法和 MySQL 有差异，不能混用。

-- 第一步：开启向量扩展（pgvector 的核心）
CREATE EXTENSION IF NOT EXISTS vector;

-- 文档表：一篇文档一行
CREATE TABLE IF NOT EXISTS documents (
  id         BIGSERIAL PRIMARY KEY,           -- PostgreSQL 自增写法
  title      TEXT        NOT NULL,
  source     TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 分块表：RAG 检索的最小单位
-- embedding 列用 vector(1024) 类型：1024 是智谱 embedding-3 的维度
CREATE TABLE IF NOT EXISTS chunks (
  id          BIGSERIAL PRIMARY KEY,
  doc_id      BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index INT    NOT NULL,
  content     TEXT   NOT NULL,
  embedding   vector(1024),                    -- 原生向量类型，不是 JSON
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- 向量索引：HNSW 算法 + 余弦距离
-- 有了它，检索时用 "ORDER BY embedding <=> 某向量" 就能快速找到最相似的块
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
  ON chunks USING hnsw (embedding vector_cosine_ops);


-- 用户表：注册用
-- password_hash 只存 Argon2 哈希，绝不存明文密码
CREATE TABLE IF NOT EXISTS users (
  id            BIGSERIAL PRIMARY KEY,
  username      VARCHAR(50) NOT NULL UNIQUE,
  password_hash TEXT        NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- 会话表：登录成功后签发 token，服务端只保存 token 的哈希
-- 保存哈希而不是原始 token：数据库万一泄露，别人也无法拿哈希来冒充登录
CREATE TABLE IF NOT EXISTS sessions (
  id          BIGSERIAL PRIMARY KEY,
  token_hash  TEXT        NOT NULL UNIQUE,          -- 唯一，防止重复
  user_id     BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at  TIMESTAMPTZ NOT NULL,                 -- 过期时间
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- 对话记录表：每条消息归属到一个用户
-- user_id 就是“数据隔离”的关键：查询时按它过滤，各看各的。
-- 必须放在 users 表之后，因为外键要引用 users(id)。
CREATE TABLE IF NOT EXISTS chat_log (
  id         BIGSERIAL PRIMARY KEY,
  user_id    BIGINT REFERENCES users(id) ON DELETE CASCADE,
  role       TEXT    NOT NULL,
  content    TEXT    NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);