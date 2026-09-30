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

from fastapi import FastAPI, File, UploadFile, HTTPException

from pydantic import BaseModel

from agent_langchain import run_agent
import db
import rag
from fastapi import Query

app = FastAPI()


class ChatRequest(BaseModel):
    """定义前端发来的 JSON 结构，例如 {"message": "现在几点？"}。"""

    message: str


@app.post("/chat")
def chat(req: ChatRequest) -> dict:
    """接收用户问题，用 RAG 检索相关知识，再交给 Agent 处理。

    注意：RAG 检索是可选的。即使数据库里没有相关文档，
    检索结果为空，Agent 也能正常回答。
    """

    # 1) 先把用户的问题存起来
    db.save_message("user", req.message)

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

    # 5) 把 Agent 的回答也存进去
    db.save_message("agent", answer)

    return {"answer": answer}


@app.get("/history")
def history(limit: int = 20) -> dict:
    """返回最近的对话记录，供前端显示历史。"""

    return {"messages": db.get_history(limit)}


@app.post("/documents/upload")
async def upload_file(file: UploadFile = File(...)) -> dict:
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