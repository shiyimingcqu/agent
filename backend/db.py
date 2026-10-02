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
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from psycopg import Connection, connect, errors

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def get_conn() -> Connection:
    """建立 PostgreSQL 连接。"""
    return connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "123456"),
        dbname=os.getenv("DB_NAME", "ai_agent"),
    )


def save_message(user_id: int, role: str, content: str) -> None:
    """保存一条消息，并标记它属于哪个用户。role 取值 "user" 或 "agent"。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_log (user_id, role, content) VALUES (%s, %s, %s)",
                (user_id, role, content),
            )
        conn.commit()
    finally:
        conn.close()


def get_history(user_id: int, limit: int = 20) -> list:
    """取出某个用户最近的 limit 条消息，按时间从早到晚返回。

    WHERE user_id = %s 就是“数据隔离”的关键：
    只查当前登录用户自己的记录，看不到别人的。
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content, created_at "
                "FROM chat_log WHERE user_id = %s ORDER BY id DESC LIMIT %s",
                (user_id, limit),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {"role": r[0], "text": r[1], "created_at": r[2].isoformat()}
        for r in reversed(rows)
    ]

def create_user(username: str, password_hash: str) -> dict:
    """插入一个新用户，返回 {"id": ..., "username": ...}。

    注意：这里传入的是 password_hash（已加密），不是明文密码。
    用户名重复时不靠"先查询有没有"，而是直接插入并捕获数据库的
    唯一约束错误，这样在并发下也不会插入重复用户。
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 参数化 SQL：%s 占位，由驱动安全转义，避免 SQL 注入
            cur.execute(
                "INSERT INTO users (username, password_hash) "
                "VALUES (%s, %s) RETURNING id, username",
                (username, password_hash),
            )
            row = cur.fetchone()
        conn.commit()
    except errors.UniqueViolation:
        # 唯一约束冲突：说明用户名已被占用
        conn.rollback()
        raise ValueError("用户名已存在")
    finally:
        conn.close()

    return {"id": row[0], "username": row[1]}

def get_user_by_username(username: str) -> dict | None:
    """按用户名查用户，返回 {"id", "username", "password_hash"}。

    找不到时返回 None，由上层决定返回什么错误。
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash FROM users WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    return {"id": row[0], "username": row[1], "password_hash": row[2]}


def create_session(token_hash: str, user_id: int, expires_at: datetime) -> None:
    """保存一条登录会话。注意传进来的是 token 的哈希，不是原始 token。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (token_hash, user_id, expires_at) "
                "VALUES (%s, %s, %s)",
                (token_hash, user_id, expires_at),
            )
        conn.commit()
    finally:
        conn.close()


def get_user_by_token(token_hash: str) -> dict | None:
    """用 token 哈希查当前登录用户；token 不存在或已过期都返回 None。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # expires_at > now() 表示还没过期；过期的会话会被视为无效
            cur.execute(
                "SELECT u.id, u.username FROM sessions s "
                "JOIN users u ON u.id = s.user_id "
                "WHERE s.token_hash = %s AND s.expires_at > now()",
                (token_hash,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    return {"id": row[0], "username": row[1]}

def delete_session(token_hash: str) -> None:
    """删除一条会话记录（登出时用）。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash,))
        conn.commit()
    finally:
        conn.close()


def delete_expired_sessions() -> None:
    """清理所有已过期的会话，避免 sessions 表无限增长。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE expires_at <= now()")
        conn.commit()
    finally:
        conn.close()
