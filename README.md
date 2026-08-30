# 🤖 coding-agent-nju

一个基于大模型的**编程智能体（Coding Agent）**，能自主写代码、执行命令、读取报错并修复，支持多轮连续对话、多会话管理，提供命令行与 Web 两种入口。

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🧠 ReAct 自主循环 | 模型「思考 → 调用工具 → 读结果 → 再思考」，报错自动修复 |
| 💬 多轮连续对话 | 跨任务记住上下文，可基于之前的工作继续 |
| 📂 多会话管理 | 新建 / 切换 / 删除会话，历史持久化到本地 `sessions/` |
| 🖥 双入口（CLI + Web）| 命令行与 Web 界面共用同一套会话历史，CLI 用命令、Web 用侧边栏管理 |
| 🛡 危险操作确认 | `rm -rf` / `del` / `format` 等危险命令需确认后才执行（前端弹框 / 终端询问） |
| ✂️ 长文本智能截断 | 工具输出过长时保留头尾，防止 Token 溢出崩溃 |
| 📊 Token 成本统计 | 实时统计每轮任务消耗的 Token |

## 🧰 技术栈

- Python 3.11+
- OpenAI SDK（兼容 DeepSeek / OpenAI 等任意兼容接口）
- FastAPI + Uvicorn（Web 后端，SSE 流式）
- 原生 HTML / CSS / JS（前端，零构建链）

## 📦 安装

```bash
pip install -r requirements.txt
```

在项目根目录创建 `.env`（不要提交到 git）：

```bash
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=https://api.deepseek.com   # 或任意兼容端点
MAX_CONTEXT_TOKENS=16000                    # 可选，上下文预算
```

默认模型为 `deepseek-chat`，可在 [agent/core.py](agent/core.py) 中修改。

## 🚀 运行

### 方式一：命令行 CLI

```bash
python main.py
```

支持多会话管理：

| 命令 | 作用 |
|------|------|
| `/new` | 新建会话 |
| `/sessions` | 列出所有会话 |
| `/use <编号>` | 切换会话 |
| `/rm <编号>` | 删除会话 |
| `/clear` | 清空当前会话 |
| `/history` | 查看当前上下文占用 |
| `/help` | 帮助 |
| `exit` | 退出 |

### 方式二：Web UI

```bash
python server.py
# 浏览器打开 http://127.0.0.1:8000
```

左侧可新建 / 切换 / 删除会话；右侧对话窗实时展示 Agent 的执行过程（思考 → 工具调用 → 执行结果 → 最终回复）。CLI 与 Web 共用同一套 `sessions/` 历史，两个入口可互换使用。

## 📁 项目结构

```
coding-agent-nju/
├── main.py              # CLI 入口
├── server.py            # FastAPI Web 服务
├── agent/
│   ├── core.py          # CodingAgent：ReAct 循环 + 流式事件
│   ├── tools.py         # 工具实现：读写文件 / 执行命令 + 智能截断
│   ├── schemas.py       # 工具 Schema（供 Function Calling）
│   └── sessions.py      # SessionManager：多会话持久化
├── static/              # 前端（index.html / style.css / app.js）
├── sessions/            # 会话数据（运行时生成，已 gitignore）
└── requirements.txt
```

## ⚙️ 工具能力

| 工具 | 功能 |
|------|------|
| `read_file` | 读取本地文件（超长自动截断） |
| `write_file` | 写入 / 覆盖本地文件 |
| `execute_command` | 执行终端命令（危险命令需确认；超长输出截断） |

## 🧠 架构设计

1. **ReAct 状态机**：[`stream_run`](agent/core.py) 是一个生成器，yield `status / tool_call / tool_result / answer / error / confirm` 事件，CLI 与 Web 复用同一核心，只是消费方式不同。
2. **上下文滑动窗口**：`_trim_context` 按完整轮次裁剪最早历史，超出预算丢弃，保证 `tool_calls` 与结果不被打散，防止上下文溢出。
3. **长文本智能截断**：`smart_truncate` 对工具输出保留头尾（报错信息通常在日志尾部），既避免 Token 溢出崩溃，又降低 API 成本。
4. **成本意识**：实时统计每轮任务的 Token 消耗，可基于此设置熔断机制（如单任务超限强制终止）。
5. **人机协作确认**：危险命令通过可注入的 `confirm` 回调确认——CLI 用终端输入、Web 用前端弹框 + SSE 往返，后端不阻塞。

## ⚠️ 安全说明

- `execute_command` 会在服务器本机执行命令，当前**无鉴权**，仅适合本机单人使用，勿直接暴露公网。
- 危险命令（`rm -rf` / `del` / `format`）默认需确认；未提供确认回调时一律拒绝。
