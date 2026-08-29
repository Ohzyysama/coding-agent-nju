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

    def run(self, task_prompt):
        messages = [
            {"role": "system", "content": "你是一个强大的编程智能体。你可以写代码并运行。如果报错，请仔细阅读错误信息（stderr），修改代码并重新尝试，直到任务成功。"},
            {"role": "user", "content": task_prompt}
        ]
        
        console.print(Panel(f"[bold cyan]任务目标：[/bold cyan] {task_prompt}", title="Agent 启动"))

        while True:
            with console.status("[bold green]Agent 正在思考中...[/bold green]", spinner="dots"):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOLS_SCHEMA,
                    tool_choice="auto"
                )
                
            msg = response.choices[0].message
            
            if not msg.tool_calls:
                console.print("\n[bold magenta] 任务完成，最终回复：[/bold magenta]")
                console.print(msg.content)
                break
                
            messages.append(msg)
            
            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                
                console.print(f"[bold yellow] 调用工具：[/bold yellow] {func_name} | 参数: {args}")
                result = TOOL_MAP[func_name](**args)
                
                preview = str(result)[:200] + ("..." if len(str(result)) > 200 else "")
                console.print(f"[dim]↳ 执行结果: {preview}[/dim]\n")
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result)
                })