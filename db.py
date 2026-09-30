"""数据库层：PostgreSQL + pgvector 的连接和读写封装。

注意：PostgreSQL 和 MySQL 的语法差异：
    - 连接参数：dbname 不是 database
    - 自增：BIGSERIAL 不是 AUTO_INCREMENT
    - 驱动：psycopg 不是 pymysql
    - 向量：vector 类型，用 <=> 算余弦距离

需要在项目根目录的 .env 里配置：
    DB_HOST=127.0.0.1
    DB_PORT=5432
    DB_USER=postgres
    DB_PASSWORD=123456
    DB_NAME=ai_agent
"""

import os

from dotenv import load_dotenv
from psycopg import Connection, connect

load_dotenv()


def get_conn() -> Connection:
    """建立 PostgreSQL 连接。"""
    return connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "123456"),
        dbname=os.getenv("DB_NAME", "ai_agent"),
    )


def save_message(role: str, content: str) -> None:
    """保存一条消息。role 取值 "user" 或 "agent"。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_log (role, content) VALUES (%s, %s)",
                (role, content),
            )
        conn.commit()
    finally:
        conn.close()


def get_history(limit: int = 20) -> list:
    """取出最近 limit 条消息，按时间从早到晚返回。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content, created_at "
                "FROM chat_log ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {"role": r[0], "text": r[1], "created_at": r[2].isoformat()}
        for r in reversed(rows)
    ]