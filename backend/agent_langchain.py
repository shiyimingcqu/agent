"""用 LangChain 重写的 DeepSeek Agent，效果与 agent.py 一模一样。

agent.py 手写了 Agent 的三要素（大模型、工具、循环），
LangChain 把这三样都封装成了现成的组件，所以代码更短。

两者的对应关系：

| agent.py（手写）        | 本文件（LangChain）                        |
| ---------------------- | ------------------------------------------ |
| get_current_time 函数  | 用 @tool 装饰的同一个函数                  |
| 手写的 TOOLS JSON      | @tool 自动从函数名和文档字符串生成 Schema  |
| run_tool 分发器        | LangChain 自动执行工具并回填结果           |
| for 循环 + messages    | AgentExecutor 内部的循环                   |

运行前请先按照 README.md 配置 DEEPSEEK_API_KEY。
"""

import os
from datetime import datetime

from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


# 从当前目录的 .env 文件读取配置，与 agent.py 完全一致。
load_dotenv()


@tool
def get_current_time() -> str:
    """读取运行程序的电脑当前日期、时间和时区。"""

    result = datetime.now().astimezone().isoformat(timespec="seconds")

    # agent.py 是在 run_tool 里打印，这里放到工具内部，让输出保持一致。
    print(f"[工具] get_current_time -> {result}")
    return result


# @tool 已经把这个普通函数变成了 LangChain 工具：
# 名称取函数名，描述取文档字符串，参数自动转成 JSON Schema。
# 这就是 agent.py 里手写 TOOLS 那一段 JSON 的等价物。
TOOLS = [get_current_time]


# 提示词模板，对应 agent.py 里的 system + user 两条消息。
# {agent_scratchpad} 是 LangChain 的占位符，用来存放“工具调用 -> 工具结果”的
# 中间过程；它等价于 agent.py 中自己往 messages 里追加 assistant / tool 消息。
PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是一个简洁、友好的中文助手。"
            "当问题涉及当前日期或时间时，必须调用工具，不要猜测。",
        ),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)


def run_agent(user_question: str) -> str:
    """让 Agent 处理一个问题，并返回最终答案。"""

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "没有找到 DEEPSEEK_API_KEY。请复制 .env.example 为 .env，"
            "然后填入你的 DeepSeek API Key。"
        )

    # DeepSeek 兼容 OpenAI 协议，所以用 ChatOpenAI，但 base_url 指向 DeepSeek；
    # 请求并不会发到 OpenAI。这与 agent.py 里的 OpenAI 客户端是同一个道理。
    llm = ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )

    # 把模型、工具、提示词组装成一个会“自主调用工具”的 Agent。
    agent = create_tool_calling_agent(llm, TOOLS, PROMPT)

    # AgentExecutor 负责跑循环：模型 -> 工具 -> 模型，直到模型给出最终答案。
    # max_iterations=5 对应 agent.py 里的 for _ in range(5)，
    # 是防止模型反复调用工具、无法结束的安全上限。
    executor = AgentExecutor(
        agent=agent,
        tools=TOOLS,
        max_iterations=5,
        verbose=False,
    )

    # 传入 {"input": ...}，是因为上面的模板用了 {input} 这个占位符。
    result = executor.invoke({"input": user_question})
    return result["output"]


if __name__ == "__main__":
    # 只有直接运行 `python agent_langchain.py` 时才执行下面两行。
    question = input("你：").strip()
    print("Agent：", run_agent(question))