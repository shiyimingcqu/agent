"""RAG 模块：文档切块 → 智谱 embedding → 存 PostgreSQL → 相似度检索

依赖：
    pip install "psycopg[binary]" httpx

环境变量（.env）：
    ZHIPU_API_KEY=你的智谱 API Key
    ZHIPU_MODEL=embedding-3

使用示例：
    # 入库
    from rag import add_document
    add_document("我的文档.txt", "这是一篇文档的内容……")

    # 检索
    from rag import search
    results = search("用户问题", top_k=5)
    for r in results:
        print(r["content"], r["score"])
"""

import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from psycopg import Connection, connect

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------- 配置 ----------
EMBEDDING_DIM = 1024                   # 智谱 embedding-3 的维度
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
ZHIPU_MODEL = os.getenv("ZHIPU_MODEL", "embedding-3")


def get_db() -> Connection:
    """建立 PostgreSQL 连接。

    注意：PostgreSQL 的连接参数名和 MySQL 不同，
    端口默认 5432（不是 MySQL 的 3306/3307）。
    """
    return connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "123456"),
        dbname=os.getenv("DB_NAME", "ai_agent"),
    )


def get_embedding(text: str) -> list[float]:
    """调用智谱 embedding-3 接口，把文本转成 1024 维向量。

    注意：智谱的 API 兼容 OpenAI 格式，所以用 httpx 直接调，
    也可以用 openai SDK（base_url 改成智谱地址）。
    """
    resp = httpx.post(
        "https://open.bigmodel.cn/api/paas/v4/embeddings",
        headers={
            "Authorization": f"Bearer {ZHIPU_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": ZHIPU_MODEL,
            "input": text,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"][0]["embedding"]  # 智谱返回格式


def chunk_text(text: str, max_chars: int = 500) -> list[str]:
    # 1. 按空行拆成段落
    paragraphs = [
        paragraph.strip()
        for paragraph in text.split("\n\n")
        if paragraph.strip()
    ]

    chunks = []

    # 当前块包含的段落
    current_paragraphs = []

    # 当前块的字符数
    current_length = 0

    for paragraph in paragraphs:
        # 如果当前块已有内容，加入新段落时还需要两个换行符
        separator_length = 2 if current_paragraphs else 0

        new_length = current_length + separator_length + len(paragraph)

        # 加入新段落后超过限制：
        # 保存当前块，然后让新段落成为下一块的开始
        if current_paragraphs and new_length > max_chars:
            chunk = "\n\n".join(current_paragraphs)
            chunks.append(chunk)

            current_paragraphs = [paragraph]
            current_length = len(paragraph)

        # 没有超过限制：继续放进当前块
        else:
            current_paragraphs.append(paragraph)
            current_length = new_length

    # 循环结束后，最后一个块还没有被保存
    if current_paragraphs:
        chunk = "\n\n".join(current_paragraphs)
        chunks.append(chunk)

    return chunks


def add_document(title: str, text: str) -> int:
    """入库一篇文档：切块 → 转向量 → 写库。

    返回新文档的 id。
    """
    if not ZHIPU_API_KEY:
        raise RuntimeError("请在 .env 中配置 ZHIPU_API_KEY")

    chunks = chunk_text(text)
    conn = get_db()
    try:
        with conn.cursor() as cur:
            # 1) 插入文档
            cur.execute(
                "INSERT INTO documents (title) VALUES (%s) RETURNING id",
                (title,),
            )
            doc_id = cur.fetchone()[0]

            # 2) 逐块：转向量 + 插入
            for i, chunk in enumerate(chunks):
                embedding = get_embedding(chunk)
                cur.execute(
                    "INSERT INTO chunks (doc_id, chunk_index, content, embedding) "
                    "VALUES (%s, %s, %s, %s::vector)",
                    (doc_id, i, chunk, embedding),
                )

        conn.commit()
        print(f"[RAG] 入库完成：{title}，共 {len(chunks)} 块")
        return doc_id
    finally:
        conn.close()


def search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """用用户问题去向量库里找最相似的 top_k 个块。

    返回 [{"content": ..., "score": ..., "doc_id": ...}, ...]
    score 是余弦相似度（1 - 距离），越接近 1 越相似。
    """
    if not ZHIPU_API_KEY:
        raise RuntimeError("请在 .env 中配置 ZHIPU_API_KEY")

    # 1) 把用户问题也转成向量
    query_vec = get_embedding(query)

    conn = get_db()
    try:
        with conn.cursor() as cur:
            # 关键：在数据库里算相似度，不用把向量读到 Python
            # <=> 是 pgvector 的余弦距离运算符
            cur.execute(
                "SELECT content, 1 - (embedding <=> %s::vector) AS score, doc_id "
                "FROM chunks "
                "ORDER BY embedding <=> %s::vector "
                "LIMIT %s",
                (query_vec, query_vec, top_k),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {"content": r[0], "score": round(r[1], 4), "doc_id": r[2]}
        for r in rows
    ]
