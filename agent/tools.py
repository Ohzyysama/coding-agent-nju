import os
import shutil
import subprocess

DANGER_KEYWORDS = ['rm -rf', 'del', 'format']

# 工具返回给模型的最大长度（字符数），超过则智能截断保留头尾
MAX_OUTPUT_LENGTH = 2000


def smart_truncate(text, max_length=MAX_OUTPUT_LENGTH):
    """智能截断：保留文本头部和尾部，因为报错信息通常在尾部。"""
    if len(text) <= max_length:
        return text
    marker = "\n\n...[系统提示：输出过长，中间部分已截断]...\n\n"
    half = (max_length - len(marker)) // 2
    return text[:half] + marker + text[-half:]


def is_dangerous_command(command):
    """判断命令是否属于危险操作，需要用户确认。"""
    command = command or ""
    return any(kw in command for kw in DANGER_KEYWORDS)


def read_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return smart_truncate(f.read())
    except Exception as e:
        return f"读取失败: {str(e)}"


def write_file(file_path, content):
    try:
        # 自动备份：覆盖前若文件已存在，先复制一份 .bak，防止模型幻觉破坏原文件
        backup_msg = ""
        if os.path.exists(file_path):
            backup_path = file_path + ".bak"
            shutil.copy2(file_path, backup_path)
            backup_msg = f"（原文件已自动备份至 {backup_path}）"

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"文件写入成功。{backup_msg}"
    except Exception as e:
        return f"写入失败: {str(e)}"


def execute_command(command):
    """执行终端命令，捕获 stderr 用于自主纠错。

    危险命令的确认由上层 stream_run 负责（CLI 用终端输入、Web 用前端确认），
    这里不再阻塞等待输入，避免 Web 场景卡死后端。
    """
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return smart_truncate(f"执行成功。输出:\n{result.stdout}")
        else:
            return smart_truncate(f"执行失败。请分析错误信息并修复代码:\n{result.stderr}")
    except Exception as e:
        return f"执行异常: {str(e)}"


def list_directory(path="."):
    """递归列出目录树（跳过隐藏目录、__pycache__、venv 等），让 Agent 了解项目结构。"""
    try:
        lines = []

        def walk(current, depth):
            if depth > 3:
                lines.append("  " * depth + "...")
                return
            entries = sorted(os.listdir(current))
            entries = [e for e in entries
                       if not e.startswith('.') and '__pycache__' not in e and e not in ('venv', 'node_modules')]
            for e in entries:
                full = os.path.join(current, e)
                if os.path.isdir(full):
                    lines.append("  " * depth + e + "/")
                    walk(full, depth + 1)
                else:
                    lines.append("  " * depth + e)

        walk(path, 0)
        return smart_truncate(f"目录结构（{path}）:\n" + "\n".join(lines))
    except Exception as e:
        return f"无法读取目录: {str(e)}"


TOOL_MAP = {
    "read_file": read_file,
    "write_file": write_file,
    "execute_command": execute_command,
    "list_directory": list_directory
}
