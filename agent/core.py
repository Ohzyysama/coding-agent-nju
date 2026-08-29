import os
import json
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from .tools import TOOL_MAP
from .schemas import TOOLS_SCHEMA

console = Console()


class CodingAgent:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )
        self.model = "deepseek-chat"
        # 上下文预算（估算 token 数），可用环境变量 MAX_CONTEXT_TOKENS 覆盖
        self.max_tokens = int(os.getenv("MAX_CONTEXT_TOKENS", "16000"))

    def _estimate_tokens(self, messages):
        total = 0
        for m in messages:
            content = m.get("content") or ""
            if isinstance(content, list):
                content = "".join(str(c.get("text", "")) for c in content if isinstance(c, dict))
            text = str(content)
            # 中文按 1 字≈1 token，其余按 4 字符≈1 token，每条消息加少量固定开销
            cjk = sum(1 for ch in text if '一' <= ch <= '鿿')
            total += cjk + (len(text) - cjk) // 4 + 4
        return total

    def _trim_context(self, messages):
        """超限时按完整轮次丢弃最早的历史，保证 tool_calls 与结果不被打散。"""
        while self._estimate_tokens(messages) > self.max_tokens:
            user_idx = [i for i, m in enumerate(messages) if m["role"] == "user"]
            if len(user_idx) <= 1:
                break
            del messages[user_idx[0]:user_idx[1]]
            console.print("[yellow] 上下文超限，已裁剪最早一轮对话。[/yellow]")

    def _message_to_dict(self, msg):
        if msg.tool_calls:
            return {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        return {"role": "assistant", "content": msg.content}

    def stream_run(self, task_prompt, messages):
        """生成器：执行一轮任务，yield 过程事件；messages 原地更新，由调用方负责持久化。

        事件类型：status / tool_call / tool_result / answer / error
        """
        messages.append({"role": "user", "content": task_prompt})
        self._trim_context(messages)

        while True:
            yield {"type": "status", "content": "thinking"}
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOLS_SCHEMA,
                    tool_choice="auto"
                )
            except Exception as e:
                yield {"type": "error", "content": f"模型调用失败: {e}"}
                return

            msg = response.choices[0].message

            if not msg.tool_calls:
                messages.append(self._message_to_dict(msg))
                yield {"type": "answer", "content": msg.content}
                return

            messages.append(self._message_to_dict(msg))

            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except Exception:
                    args = {}

                yield {"type": "tool_call", "name": func_name, "args": args}

                try:
                    result = TOOL_MAP[func_name](**args)
                except Exception as e:
                    result = f"工具执行异常: {e}"

                yield {"type": "tool_result", "content": str(result)}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result)
                })

    def run(self, task_prompt, messages):
        """CLI 封装：消费 stream_run 事件并用 rich 打印。"""
        console.print(Panel(f"[bold cyan]任务目标：[/bold cyan] {task_prompt}", title="Agent 启动"))

        for event in self.stream_run(task_prompt, messages):
            etype = event["type"]
            if etype == "status":
                console.print("[dim]Agent 正在思考中...[/dim]")
            elif etype == "tool_call":
                console.print(f"[bold yellow] 调用工具：[/bold yellow] {event['name']} | 参数: {event['args']}")
            elif etype == "tool_result":
                content = str(event["content"])
                preview = content[:200] + ("..." if len(content) > 200 else "")
                console.print(f"[dim]↳ 执行结果: {preview}[/dim]\n")
            elif etype == "answer":
                console.print("\n[bold magenta] 任务完成，最终回复：[/bold magenta]")
                console.print(event["content"])
            elif etype == "error":
                console.print(f"\n[red]错误：[/red] {event['content']}")
