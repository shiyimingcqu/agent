# 最小 DeepSeek Agent

这是一个面向初学者的最小 Agent。它只有一个能力：在需要时调用本机 Python
函数读取当前时间，然后根据真实结果回答用户。

## 它为什么算 Agent

普通聊天程序通常只有一步：

```text
用户问题 -> 大模型回答
```

这个程序多了“自主选择工具并继续执行”的循环：

```text
用户问题
   ↓
DeepSeek 判断是否需要工具
   ↓ 需要
Python 执行工具
   ↓
工具结果交回 DeepSeek
   ↓
DeepSeek 给出最终答案
```

关键点是：代码没有写死“用户问时间就调用函数”。是否调用工具由模型根据问题决定。

## 1. 准备环境

请先确认已安装 Python 3.10 或更高版本：

```powershell
python --version
```

在项目目录创建虚拟环境：

```powershell
python -m venv .venv
```

激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

## 2. 配置 DeepSeek API Key

先复制配置模板：

```powershell
Copy-Item .env.example .env
```

打开新生成的 `.env`，把占位文字替换成你自己的 DeepSeek API Key：

```dotenv
DEEPSEEK_API_KEY=你的真实Key
DEEPSEEK_MODEL=deepseek-flash
```

`.gitignore` 已经忽略 `.env`，可以防止你不小心把密钥提交到 Git。

## 3. 运行

```powershell
python agent.py
```

建议先测试这个问题：

```text
现在几点？
```

你会看到类似输出：

```text
你：现在几点？
[工具] get_current_time -> 2026-09-28T23:30:00+08:00
Agent：现在是 2026 年 9 月 28 日 23:30（UTC+8）。
```

再试一个不需要工具的问题，例如“用一句话解释变量”。这次通常不会出现 `[工具]`，
因为模型可以直接回答。

## 4. 阅读代码的推荐顺序

打开 `agent.py`，按这个顺序阅读：

1. `get_current_time`：真正干活的普通 Python 函数。
2. `TOOLS`：把函数的能力介绍给大模型。
3. `run_tool`：把模型要求调用的工具名映射到 Python 函数。
4. `run_agent`：保存消息并反复执行“模型 -> 工具 -> 模型”的循环。
5. 文件最下面的 `if __name__ == "__main__"`：接收终端输入并启动 Agent。

## 5. 适合你的下一个练习

完全理解当前版本后，可以自己添加一个 `calculate` 工具。先写普通 Python 函数，
再把它加入 `TOOLS`，最后在 `run_tool` 中增加分支。这三个改动正好对应：
实现能力、向模型描述能力、允许程序执行能力。

## 安全提醒

- API 调用可能产生费用，请在 DeepSeek 平台设置合理的余额和用量限制。
- 不要把 API Key 写入 `agent.py`、聊天截图或 Git 提交。
- 真实项目中，执行文件、数据库、网络请求等工具前，需要校验参数并限制权限。

实现依据：[DeepSeek 官方 Tool Calls 文档](https://api-docs.deepseek.com/guides/tool_calls/)。
