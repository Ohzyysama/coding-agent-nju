import os
import json
import time
import uuid

SESSIONS_DIR = "sessions"

SYSTEM_PROMPT = (
    "你是一个强大的编程智能体。你可以写代码并运行。"
    "如果报错，请仔细阅读错误信息（stderr），修改代码并重新尝试，直到任务成功。"
    "你会记住之前对话的内容，支持连续多轮协作，可基于上下文继续之前的工作。"
)


def make_title(message):
    """从首条用户消息生成会话标题，过长用省略号。"""
    text = message.strip()
    if not text:
        return "新对话"
    if len(text) <= 20:
        return text
    return text[:19] + "…"


class SessionManager:
    """多会话持久化：每个会话一个 JSON 文件，存于 sessions/ 目录。"""

    def __init__(self, base_dir=SESSIONS_DIR):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, session_id):
        return os.path.join(self.base_dir, f"{session_id}.json")

    def get(self, session_id):
        try:
            with open(self._path(session_id), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def get_or_create(self, session_id):
        session = self.get(session_id)
        if session:
            return session
        session = {
            "id": session_id,
            "title": "新对话",
            "created_at": time.time(),
            "updated_at": time.time(),
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
        }
        self.save(session)
        return session

    def create(self):
        return self.get_or_create(uuid.uuid4().hex)

    def list(self):
        sessions = []
        for name in os.listdir(self.base_dir):
            if not name.endswith(".json"):
                continue
            session = self.get(name[:-5])
            if not session:
                continue
            sessions.append({
                "id": session["id"],
                "title": session.get("title", "新对话"),
                "created_at": session.get("created_at", 0),
                "updated_at": session.get("updated_at", 0),
                "message_count": len(session.get("messages", [])),
            })
        sessions.sort(key=lambda s: s["updated_at"], reverse=True)
        return sessions

    def save(self, session):
        session["updated_at"] = time.time()
        with open(self._path(session["id"]), "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)

    def delete(self, session_id):
        try:
            os.remove(self._path(session_id))
            return True
        except Exception:
            return False

    def clear(self, session_id):
        session = self.get(session_id)
        if not session:
            return None
        session["messages"] = [{"role": "system", "content": SYSTEM_PROMPT}]
        session["title"] = "新对话"
        self.save(session)
        return session
