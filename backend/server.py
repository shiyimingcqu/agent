"""把 Agent 接到网页上的最小后端：一个 FastAPI 应用。

整体链路：

    浏览器 (Vue 前端)
        │  fetch POST /chat  {"message": "现在几点？"}
        ▼
    本文件 (FastAPI)  ──调用──▶  agent.run_agent()  ──▶  DeepSeek
        │                └──调用──▶  db.save_message() ──▶  PostgreSQL
        │                └──调用──▶  rag.search()      ──▶  向量检索
        │  返回 {"answer": "现在是……"}
        ▼
    浏览器把答案显示出来

启动方式（请在项目根目录执行）：
    python -m uvicorn server:app --reload
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, FastAPI, File, HTTPException, Response, UploadFile
from pydantic import BaseModel
from pwdlib import PasswordHash

from agent_langchain import run_agent
import db
import rag
from fastapi import Query

app = FastAPI()

# 密码哈希器：Argon2 算法，FastAPI 官方教程推荐。
# 哈希时会自动加随机盐，所以同一个密码每次生成的哈希都不同，
# 因此验证密码只能用 verify()，不能自己重新 hash 后比对。
password_hasher = PasswordHash.recommended()


class ChatRequest(BaseModel):
    """定义前端发来的 JSON 结构，例如 {"message": "现在几点？"}。"""

    message: str


class RegisterRequest(BaseModel):
    """注册请求结构：{"username": "...", "password": "..."}。"""

    username: str
    password: str


class LoginRequest(BaseModel):
    """登录请求结构：{"username": "...", "password": "..."}。"""

    username: str
    password: str


# 登录会话有效期：7 天
SESSION_DAYS = 7


@app.post("/auth/register")
def register(req: RegisterRequest) -> dict:
    """注册新用户：校验长度 → 哈希密码 → 入库（绝不返回密码或哈希）。"""

    # 1) 校验用户名和密码长度
    if not (3 <= len(req.username) <= 50):
        raise HTTPException(status_code=400, detail="用户名长度需为 3-50 个字符")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="密码至少需要 8 个字符")

    # 2) 计算密码哈希。这里得到的是 Argon2 哈希串，不是明文密码。
    password_hash = password_hasher.hash(req.password)

    # 3) 用参数化 SQL 插入。
    #    用户名重复时，数据库唯一约束会报错，由 db.create_user 转成 ValueError。
    try:
        user = db.create_user(req.username, password_hash)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # 4) 只返回用户 ID 和用户名，不返回哈希
    return user


@app.post("/auth/login")
def login(req: LoginRequest, response: Response) -> dict:
    """登录：核对密码 → 签发随机 token → 存哈希 → 写入 HttpOnly Cookie。"""

    # 1) 按用户名查用户
    user = db.get_user_by_username(req.username)

    # 2) 验证密码（用的是 verify，不能重新 hash 后比对，因为盐是随机的）。
    #    "用户不存在" 和 "密码错误" 都返回同样的 401，
    #    避免攻击者从提示差异判断某个用户名是否存在。
    if user is None or not password_hasher.verify(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 3) 生成不可预测的随机凭证。
    #    绝对不能用 user_id 这类可猜的值当 token，否则谁都能伪造登录态。
    token = secrets.token_urlsafe(32)

    # 4) 数据库只存 token 的哈希（SHA-256）：
    #    这样数据库泄露时，拿到哈希也无法反推出能用的原始 token。
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    db.delete_expired_sessions()          # 顺手清理已过期的会话
    db.create_session(token_hash, user["id"], expires_at)

    # 5) 原始 token 通过 Cookie 交给浏览器。
    #    httponly: 前端 JS 读不到，降低被 XSS 偷走的风险
    #    samesite: 跨站请求不携带该 Cookie，缓解 CSRF
    #    secure  : 本地 HTTP 练习先设 False；一旦上 HTTPS 必须改 True
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=SESSION_DAYS * 24 * 3600,
        path="/",
    )

    return {"id": user["id"], "username": user["username"]}


def get_current_user(session: str | None = Cookie(default=None)) -> dict:
    """从请求 Cookie 解析出当前登录用户；未登录或会话失效则返回 401。

    这是一个 FastAPI "依赖"：接口只要在参数里写
        user: dict = Depends(get_current_user)
    就会先执行它——通过则把用户对象传进接口，不通过就直接返回 401。
    这样保护接口，不用在每个函数里重复写一遍解析逻辑。
    """
    if not session:
        raise HTTPException(status_code=401, detail="未登录")

    token_hash = hashlib.sha256(session.encode()).hexdigest()
    user = db.get_user_by_token(token_hash)
    if user is None:
        raise HTTPException(status_code=401, detail="登录已失效")

    return user


@app.get("/auth/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    """返回当前登录用户。前端用它判断该显示登录页还是聊天页。"""
    return user


@app.post("/auth/logout")
def logout(response: Response, session: str | None = Cookie(default=None)) -> dict:
    """登出：删除服务端会话记录，并清除浏览器里的 Cookie。"""
    if session:
        token_hash = hashlib.sha256(session.encode()).hexdigest()
        db.delete_session(token_hash)

    # 让浏览器立刻丢弃这个 Cookie（max_age=0）
    response.delete_cookie("session", path="/")
    return {"detail": "已登出"}


@app.post("/chat")
def chat(req: ChatRequest, user: dict = Depends(get_current_user)) -> dict:
    """接收用户问题，用 RAG 检索相关知识，再交给 Agent 处理。

    注意：RAG 检索是可选的。即使数据库里没有相关文档，
    检索结果为空，Agent 也能正常回答。
    """

    # 1) 先把用户的问题存起来（记录归属到当前登录用户）
    db.save_message(user["id"], "user", req.message)

    # 2) RAG 检索：从向量库里找最相关的知识块
    #    top_k=3 表示取最相似的 3 个块；太少可能漏信息，太多会撑爆 prompt
    knowledge = rag.search(req.message, top_k=3)

    # 3) 把检索到的知识拼成 prompt 前缀
    #    如果没检索到结果，knowledge 为空列表，就跳过这一步
    if knowledge:
        context = "\n\n".join(
            f"【参考资料 {i+1}】{k['content']}"
            for i, k in enumerate(knowledge)
        )
        prompt_with_knowledge = (
            f"请基于以下参考资料回答用户问题。"
            f"如果参考资料里没有相关信息，就用自己的知识回答。\n\n"
            f"{context}\n\n"
            f"用户问题：{req.message}"
        )
    else:
        prompt_with_knowledge = req.message

    # 4) 调 Agent 拿回答（Agent 收到的是拼了知识的 prompt）
    answer = run_agent(prompt_with_knowledge)

    # 5) 把 Agent 的回答也存进去（同样归属到当前用户）
    db.save_message(user["id"], "agent", answer)

    return {"answer": answer}


@app.get("/history")
def history(limit: int = 20, user: dict = Depends(get_current_user)) -> dict:
    """返回当前用户最近的对话记录，供前端显示历史。"""

    return {"messages": db.get_history(user["id"], limit)}


@app.post("/documents/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
) -> dict:
    # 1. 文件名可以作为文档标题
    title = file.filename or "未命名文档"

    # 2. 上传文件读出来是 bytes
    content = await file.read()

    # 3. 拒绝空文件
    if not content:
        raise HTTPException(status_code=400, detail="上传的文件是空文件")

    # 4. bytes 转换为 str
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件不是 UTF-8 编码")

    # 5. 把标题和文本交给现有的 RAG 入库函数
    document_id = rag.add_document(title, text)

    return {
        "document_id": document_id,
        "filename": title,
        "characters": len(text),
        "status": "indexed",
    }



@app.post("/search")
def searchfile(
    query: str = Query(min_length=1, max_length=500),
    top_k: int = Query(default=5, ge=1, le=10),
):
    return {
        "results": rag.search(query, top_k=top_k)
    }