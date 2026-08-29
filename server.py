import json
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


class ChatRequest(BaseModel):
    message: str


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


@app.post("/api/sessions/{session_id}/chat")
def chat(session_id: str, req: ChatRequest):
    session = manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 首条用户消息时用其前 20 字生成标题
    has_user = any(m["role"] == "user" for m in session["messages"])
    if not has_user:
        session["title"] = (req.message.strip()[:20] or "新对话")

    def gen():
        try:
            for event in agent.stream_run(req.message, session["messages"]):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            manager.save(session)

    return StreamingResponse(gen(), media_type="text/event-stream")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
