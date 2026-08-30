import os
import sys
import time

# Windows 下强制 UTF-8 输出，避免 rich 渲染 Markdown 时因 GBK 编码报错
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from rich.console import Console

from agent.core import CodingAgent
from agent.sessions import SessionManager, make_title


def time_ago(ts):
    diff = time.time() - ts
    if diff < 60:
        return "刚刚"
    if diff < 3600:
        return f"{int(diff // 60)} 分钟前"
    if diff < 86400:
        return f"{int(diff // 3600)} 小时前"
    return f"{int(diff // 86400)} 天前"


HELP_TEXT = (
    "[bold]可用命令：[/bold]\n"
    "  /new        新建会话\n"
    "  /sessions   列出所有会话\n"
    "  /use <编号>  切换会话\n"
    "  /rm <编号>   删除会话\n"
    "  /clear      清空当前会话\n"
    "  /history    查看当前上下文占用\n"
    "  /help       显示本帮助\n"
    "  exit        退出"
)


if __name__ == "__main__":
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("错误: 找不到 OPENAI_API_KEY。请检查 .env 文件。")
        exit(1)

    agent = CodingAgent()
    manager = SessionManager()
    console = Console()

    # 启动：有历史会话则加载最近一个，否则新建
    sessions = manager.list()
    if sessions:
        current = manager.get(sessions[0]["id"])
        console.print(f"[dim]已加载最近会话：[/dim][cyan]{current['title']}[/cyan]")
    else:
        current = manager.create()
        console.print("[dim]已新建会话，开始你的第一个任务吧。[/dim]")

    console.print("\n[bold blue]=== 欢迎使用编程智能体（多会话命令行）===[/bold blue]")
    console.print("[dim]输入 /help 查看命令，直接输入编程任务即可开始。[/dim]")

    while True:
        try:
            task = input("\n请输入编程任务: ")
            if task.lower() in ['exit', 'quit']:
                break
            if not task.strip():
                continue

            cmd = task.strip()
            parts = cmd.split(maxsplit=1)
            head = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            # ---- 命令处理 ----
            if head == '/new':
                current = manager.create()
                console.print("[bold green]已新建会话。[/bold green]")
                continue

            if head == '/sessions':
                sessions = manager.list()
                if not sessions:
                    console.print("[dim]暂无历史会话。[/dim]")
                    continue
                for i, s in enumerate(sessions, 1):
                    mark = "  [yellow]← 当前[/yellow]" if s["id"] == current["id"] else ""
                    console.print(
                        f"  [bold]{i}[/bold]. {s['title']}  "
                        f"[dim]({time_ago(s['updated_at'])} · {s['message_count']} 条消息)[/dim]{mark}"
                    )
                continue

            if head == '/use':
                sessions = manager.list()
                if not (arg.isdigit() and 1 <= int(arg) <= len(sessions)):
                    console.print("[yellow]用法: /use <编号>，先用 /sessions 查看编号。[/yellow]")
                    continue
                current = manager.get(sessions[int(arg) - 1]["id"])
                console.print(f"[bold green]已切换到会话：[/bold green][cyan]{current['title']}[/cyan]")
                continue

            if head == '/rm':
                sessions = manager.list()
                if not (arg.isdigit() and 1 <= int(arg) <= len(sessions)):
                    console.print("[yellow]用法: /rm <编号>，先用 /sessions 查看编号。[/yellow]")
                    continue
                target = sessions[int(arg) - 1]
                manager.delete(target["id"])
                console.print(f"[bold red]已删除会话：[/bold red]{target['title']}")
                if target["id"] == current["id"]:
                    remaining = manager.list()
                    current = manager.get(remaining[0]["id"]) if remaining else manager.create()
                    console.print(f"[dim]已切换到：[/dim][cyan]{current['title']}[/cyan]")
                continue

            if head == '/clear':
                current = manager.clear(current["id"])
                console.print("[bold green]对话历史已清空，上下文已重置。[/bold green]")
                continue

            if head == '/history':
                est = agent._estimate_tokens(current["messages"])
                console.print(
                    f"[cyan]当前会话：[/cyan]{current['title']} · {len(current['messages'])} 条消息，"
                    f"约 {est} token（上限 {agent.max_tokens}）"
                )
                continue

            if head == '/help':
                console.print(HELP_TEXT)
                continue

            if head.startswith('/'):
                console.print(f"[yellow]未知命令: {cmd}，输入 /help 查看帮助。[/yellow]")
                continue

            # ---- 正常任务 ----
            has_user = any(m["role"] == "user" for m in current["messages"])
            if not has_user:
                current["title"] = make_title(cmd)

            agent.run(cmd, current["messages"])
            manager.save(current)

        except KeyboardInterrupt:
            manager.save(current)
            print("\n检测到强制中断，历史已保存，程序退出。")
            break
        except Exception as e:
            print(f"\n系统发生错误: {e}")
