import json
import threading
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.core import CodingAgent
from agent.sessions import SessionManager

load_dotenv()

app = FastAPI()
agent = CodingAgent()
manager = SessionManager()

STATIC_DIR = Path(__file__).parent / "static"

# session_id -> {"event": threading.Event, "approved": bool, "command": str}
PENDING_CONFIRMS = {}


class ChatRequest(BaseModel):
    message: str


class ConfirmRequest(BaseModel):
    approved: bool


def make_web_confirm(session_id):
    """返回一个 confirm 回调：阻塞等待前端通过 /confirm 端点回应。"""
    def confirm(command):
        ev = threading.Event()
        PENDING_CONFIRMS[session_id] = {"event": ev, "approved": False, "command": command}
        # 等待前端确认；超时（300s）默认拒绝
        if not ev.wait(timeout=300):
            PENDING_CONFIRMS.pop(session_id, None)
            return False
        return PENDING_CONFIRMS.pop(session_id, {}).get("approved", False)
    return confirm


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/sessions")
def list_sessions():
    return manager.list()


@app.post("/api/sessions")
def create_session():
    session = manager.create()
    return {"id": session["id"], "title": session["title"]}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    session = manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    if not manager.delete(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


@app.post("/api/sessions/{session_id}/confirm")
def confirm_session(session_id: str, req: ConfirmRequest):
    pending = PENDING_CONFIRMS.get(session_id)
    if not pending:
        raise HTTPException(status_code=409, detail="没有待确认的危险命令")
    pending["approved"] = req.approved
    pending["event"].set()
    return {"ok": True}


@app.post("/api/sessions/{session_id}/chat")
def chat(session_id: str, req: ChatRequest):
    session = manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 首条用户消息时用其前 20 字生成标题，过长用省略号
    has_user = any(m["role"] == "user" for m in session["messages"])
    if not has_user:
        text = req.message.strip()
        if not text:
            session["title"] = "新对话"
        elif len(text) <= 20:
            session["title"] = text
        else:
            session["title"] = text[:19] + "…"

    def gen():
        try:
            for event in agent.stream_run(req.message, session["messages"], confirm=make_web_confirm(session_id)):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            manager.save(session)

    return StreamingResponse(gen(), media_type="text/event-stream")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
