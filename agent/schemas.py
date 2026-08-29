TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "在本地终端执行命令行指令（如 python xxx.py, pip install xxx 等）",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "要执行的命令"}},
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "将代码或文本写入本地文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "要写入的完整内容"}
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取本地文件内容",
            "parameters": {
                "type": "object",
                "properties": {"file_path": {"type": "string", "description": "文件路径"}},
                "required": ["file_path"]
            }
        }
    }
]