import os
from dotenv import load_dotenv
from agent.core import CodingAgent
from agent.sessions import SessionManager
from rich.console import Console

CLI_SESSION_ID = "cli"

if __name__ == "__main__":
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("错误: 找不到 OPENAI_API_KEY。请检查 .env 文件。")
        exit(1)

    agent = CodingAgent()
    manager = SessionManager()
    console = Console()

    session = manager.get_or_create(CLI_SESSION_ID)

    console.print("\n[bold blue]=== 欢迎使用编程智能体（连续对话模式）===[/bold blue]")
    console.print("[dim]命令: /clear 清空历史 | /history 查看上下文 | exit 退出[/dim]")

    while True:
        try:
            task = input("\n请输入编程任务: ")
            if task.lower() in ['exit', 'quit']:
                break
            if not task.strip():
                continue

            if task.strip() == '/clear':
                session = manager.clear(CLI_SESSION_ID)
                console.print("[bold green] 对话历史已清空，上下文已重置。[/bold green]")
                continue
            if task.strip() == '/history':
                est = agent._estimate_tokens(session["messages"])
                console.print(
                    f"[cyan]当前上下文：[/cyan] {len(session['messages'])} 条消息，"
                    f"约 {est} token（上限 {agent.max_tokens}）。"
                )
                continue

            agent.run(task, session["messages"])
            manager.save(session)

        except KeyboardInterrupt:
            manager.save(session)
            print("\n检测到强制中断，历史已保存，程序退出。")
            break
        except Exception as e:
            print(f"\n系统发生错误: {e}")
