# backend/gateway_mock.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import time

app = FastAPI(title="Gateway Mock", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

class RunReq(BaseModel):
    query: str

class RunResp(BaseModel):
    steps: list[str]
    answer: str

@app.post("/run", response_model=RunResp)
def run(req: RunReq):
    q = req.query.strip()
    # 这里模拟“打开网页/搜索/调用RAG”等步骤
    steps = [
        f"正在打开网页：检索 {q}",
        "正在搜索相关页面与FAQ…",
        "正在调用RAG检索知识库…",
        "正在综合信息并生成答案…",
    ]
    # 这里你可以替换为真正的 RAG/模型推理
    # 例如：从 SQLite FTS/向量库查片段 → 拼接答案
    answer = f"【RAG回答】关于“{q}”的结果示例：\n- 示例要点 A\n- 示例要点 B\n（此回答来自网关 mock，可替换为真实模型/RAG）"
    # 故意sleep以便前端有时间显示“动作”
    time.sleep(0.2)
    return RunResp(steps=steps, answer=answer)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8077, reload=False)
