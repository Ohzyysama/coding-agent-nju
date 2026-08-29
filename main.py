import os
from dotenv import load_dotenv
from agent.core import CodingAgent
from rich.console import Console

if __name__ == "__main__":
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("错误: 找不到 OPENAI_API_KEY。请检查 .env 文件。")
        exit(1)

    agent = CodingAgent()
    console = Console()
    
    console.print("\n[bold blue]=== 欢迎使用编程智能体 ===[/bold blue]")
    while True:
        try:
            task = input("\n请输入编程任务 (输入 'exit' 退出): ")
            if task.lower() in ['exit', 'quit']:
                break
            if not task.strip():
                continue
            agent.run(task)
            
        except KeyboardInterrupt:
            print("\n检测到强制中断，程序退出。")
            break
        except Exception as e:
            print(f"\n系统发生错误: {e}")