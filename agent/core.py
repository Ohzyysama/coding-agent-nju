import os
import json
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from .tools import TOOL_MAP, is_dangerous_command
from .schemas import TOOLS_SCHEMA

console = Console()


def _format_args(args, max_len=60):
    """格式化工具参数，超长参数截断显示，避免在终端刷屏。"""
    parts = []
    for key, value in args.items():
        text = str(value)
        if len(text) > max_len:
            text = f"{text[:max_len]}…（共 {len(text)} 字）"
        parts.append(f"{key}={text}")
    return ", ".join(parts)


class CodingAgent:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )
        self.model = "deepseek-chat"
        # 上下文预算（估算 token 数），可用环境变量 MAX_CONTEXT_TOKENS 覆盖
        self.max_tokens = int(os.getenv("MAX_CONTEXT_TOKENS", "16000"))
        self.total_tokens = 0  # 累计 Token 消耗（跨任务，用于成本统计）
        self.max_steps = int(os.getenv("MAX_STEPS", "15"))  # 单次任务最大模型调用步数，防死循环

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

    def _call_tool(self, func_name, args):
        try:
            return TOOL_MAP[func_name](**args)
        except Exception as e:
            return f"工具执行异常: {e}"

    def stream_run(self, task_prompt, messages, confirm=None, max_steps=None):
        """生成器：执行一轮任务，yield 过程事件；messages 原地更新，由调用方负责持久化。

        confirm: 可选回调 confirm(command) -> bool，用于危险命令确认。
                未提供时危险命令一律拒绝（安全默认）。
        max_steps: 单次任务最大模型调用步数，超过则熔断，防止死循环。

        事件类型：status / tool_call / confirm / tool_result / answer / limit / error
        """
        messages.append({"role": "user", "content": task_prompt})
        self._trim_context(messages)
        task_tokens = 0
        max_steps = max_steps or self.max_steps
        step_count = 0

        while True:
            # 熔断：防止模型陷入死循环无限消耗 Token
            if step_count >= max_steps:
                yield {"type": "limit", "content": f"触发熔断：任务超过最大步数（{max_steps} 步），已强制终止以防止死循环。"}
                return

            step_count += 1
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

            if response.usage:
                self.total_tokens += response.usage.total_tokens
                task_tokens += response.usage.total_tokens

            msg = response.choices[0].message

            if not msg.tool_calls:
                messages.append(self._message_to_dict(msg))
                yield {"type": "answer", "content": msg.content, "tokens": task_tokens}
                return

            messages.append(self._message_to_dict(msg))

            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except Exception:
                    args = {}

                yield {"type": "tool_call", "name": func_name, "args": args}

                # 危险命令：先请求确认，再决定是否执行
                command = args.get("command", "") if func_name == "execute_command" else ""
                if func_name == "execute_command" and is_dangerous_command(command):
                    yield {"type": "confirm", "command": command}
                    allowed = bool(confirm(command)) if confirm else False
                    if not allowed:
                        result = "执行被用户拒绝。"
                    else:
                        result = self._call_tool(func_name, args)
                else:
                    result = self._call_tool(func_name, args)

                yield {"type": "tool_result", "content": str(result)}
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result)
                })

    def run(self, task_prompt, messages):
        """CLI 封装：消费 stream_run 事件并用 rich 打印，危险命令用终端输入确认。"""
        console.print(Panel(f"[bold cyan]任务目标：[/bold cyan] {task_prompt}", title="Agent 启动"))

        def cli_confirm(command):
            console.print(f"\n[bold red] 警告：[/bold red] Agent 试图执行危险命令 `{command}`。")
            user_input = input("是否允许? (y/n): ")
            return user_input.lower() == 'y'

        for event in self.stream_run(task_prompt, messages, confirm=cli_confirm):
            etype = event["type"]
            if etype == "status":
                console.print("[dim]Agent 正在思考中...[/dim]")
            elif etype == "confirm":
                # 确认由 cli_confirm 的 input 完成，这里无需额外处理
                continue
            elif etype == "tool_call":
                console.print(f"[bold yellow] 调用工具：[/bold yellow] {event['name']} | 参数: {_format_args(event['args'])}")
            elif etype == "tool_result":
                content = str(event["content"])
                preview = content[:200] + ("..." if len(content) > 200 else "")
                console.print(f"[dim]↳ 执行结果: {preview}[/dim]\n")
            elif etype == "answer":
                console.print("\n[bold magenta] 任务完成，最终回复：[/bold magenta]")
                if event["content"]:
                    console.print(Markdown(event["content"]))
                if event.get("tokens"):
                    console.print(f"[dim]本次任务消耗 Token: {event['tokens']}（累计 {self.total_tokens}）[/dim]")
            elif etype == "limit":
                console.print(f"\n[bold red]❌ {event['content']}[/bold red]")
            elif etype == "error":
                console.print(f"\n[red]错误：[/red] {event['content']}")
