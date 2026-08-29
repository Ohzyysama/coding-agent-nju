import subprocess

def read_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"读取失败: {str(e)}"

def write_file(file_path, content):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return "文件写入成功。"
    except Exception as e:
        return f"写入失败: {str(e)}"

def execute_command(command):
    """执行终端命令，捕获 stderr 用于自主纠错"""
    danger_keywords = ['rm -rf', 'del', 'format']
    if any(kw in command for kw in danger_keywords):
        user_input = input(f"\n 警告：Agent 试图执行危险命令 `{command}`。是否允许? (y/n): ")
        if user_input.lower() != 'y':
            return "执行被用户拒绝。"

    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return f"执行成功。输出:\n{result.stdout}"
        else:
            return f"执行失败。请分析错误信息并修复代码:\n{result.stderr}"
    except Exception as e:
        return f"执行异常: {str(e)}"

TOOL_MAP = {
    "read_file": read_file,
    "write_file": write_file,
    "execute_command": execute_command
}