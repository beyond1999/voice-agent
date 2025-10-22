from __future__ import annotations
import os
import time
import json
from typing import List, Dict, Optional, Tuple
import traceback
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import httpx

from function_call.function_call_register import function_map

# ================== 运行模式开关 ==================
# 本地 / 云端（OpenAI 兼容）二选一
USE_LOCAL_MODEL = os.getenv("USE_LOCAL_MODEL", "true").lower() in ("1", "true", "yes")

# ================== 统一配置 ==================
# 本地默认：llama.cpp 服务
LOCAL_LLAMA_BASE_DEFAULT = "http://127.0.0.1:8003"
LOCAL_LLAMA_MODEL_DEFAULT = "qwen2.5-3b-instruct"

# 云端默认：通义千问 DashScope 兼容模式（你也可改为 OpenAI / DeepSeek 等）
CLOUD_BASE_DEFAULT = "https://dashscope.aliyuncs.com/compatible-mode/v1"
CLOUD_MODEL_DEFAULT = "qwen2.5-32b-instruct"  # 换成你账户可用的模型名
CLOUD_AUTH_SCHEME_DEFAULT = "Bearer"

# 读环境变量（两种模式共享这套变量名）
LLAMA_BASE = os.getenv("LLAMA_BASE", LOCAL_LLAMA_BASE_DEFAULT if USE_LOCAL_MODEL else CLOUD_BASE_DEFAULT)
LLAMA_MODEL = os.getenv("LLAMA_MODEL", LOCAL_LLAMA_MODEL_DEFAULT if USE_LOCAL_MODEL else CLOUD_MODEL_DEFAULT)
LLAMA_TIMEOUT = float(os.getenv("LLAMA_TIMEOUT", "30"))

# 云端鉴权（仅在 USE_LOCAL_MODEL = false 时使用）
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_AUTH_SCHEME = os.getenv("LLM_AUTH_SCHEME", CLOUD_AUTH_SCHEME_DEFAULT)

# 是否允许回退到 /completion（仅本地建议启用）
USE_LEGACY_FALLBACK = (os.getenv("USE_LEGACY_FALLBACK", "1") == "1") if USE_LOCAL_MODEL else False

# ================== 简易幂等缓存（内存） ==================
_IDEM: Dict[str, Tuple[float, Dict]] = {}
IDEM_TTL = 600.0  # 10 min

def _gc_idem():
    now = time.time()
    for k, (ts, _) in list(_IDEM.items()):
        if now - ts > IDEM_TTL:
            _IDEM.pop(k, None)

# ================== Pydantic 模型 ==================
class Msg(BaseModel):
    role: str
    content: str

class ChatReq(BaseModel):
    messages: List[Msg] = Field(..., description="OpenAI 风格 messages")
    session_id: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 512

class ChatResp(BaseModel):
    text: str
    model: str
    cached: bool = False

# ================== FastAPI 应用 ==================
app = FastAPI(title="LLM Module (local/cloud switch)", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mode": "local" if USE_LOCAL_MODEL else "cloud",
        "llama_base": LLAMA_BASE,
        "llama_model": LLAMA_MODEL,
        "legacy_fallback": USE_LEGACY_FALLBACK,
        "api_key_present": bool(LLM_API_KEY) if not USE_LOCAL_MODEL else None,
    }

# ------------------ 调用适配 ------------------
async def _chat_via_openai_compat(req: ChatReq) -> Tuple[str, str]:
    """
    既可打本地 llama.cpp（无鉴权），也可打云端 OpenAI 兼容 API（需要 Authorization）。
    """
    url = f"{LLAMA_BASE.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": LLAMA_MODEL,
        "messages": [m.model_dump() for m in req.messages],
        "temperature": req.temperature or 0.7,
        "max_tokens": req.max_tokens or 512,
        "stream": False,
    }

    headers = {"Content-Type": "application/json"}
    if not USE_LOCAL_MODEL:
        # 云端模式需要鉴权
        if not LLM_API_KEY:
            raise PermissionError("LLM_API_KEY is empty. Please set your API key when USE_LOCAL_MODEL=false.")
        headers["Authorization"] = f"{LLM_AUTH_SCHEME} {LLM_API_KEY}"

    async with httpx.AsyncClient(timeout=LLAMA_TIMEOUT) as client:
        r = await client.post(url, json=payload, headers=headers)

        if r.status_code == 404:
            # 本地可能没有开启 compat 接口；云端一般不会返回 404 路径不存在
            raise FileNotFoundError("/v1/chat/completions not found")

        if r.status_code in (401, 403):
            raise PermissionError(f"auth failed: {r.status_code} {r.text}")

        r.raise_for_status()
        data = r.json()
        text = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        used_model = data.get("model", LLAMA_MODEL)
        return text, used_model

def _to_legacy_prompt(messages: List[Msg]) -> str:
    sys = next((m.content for m in messages if m.role == "system"), "")
    parts = []
    if sys:
        parts.append(f"System: {sys}")
    for m in messages:
        if m.role == "user":
            parts.append(f"User: {m.content}")
        elif m.role == "assistant":
            parts.append(f"Assistant: {m.content}")
    parts.append("Assistant:")
    return "".join(parts)

async def _chat_via_legacy_completion(req: ChatReq) -> Tuple[str, str]:
    # llama.cpp 旧接口 /completion
    url = f"{LLAMA_BASE.rstrip('/')}/completion"
    prompt = _to_legacy_prompt(req.messages)
    payload = {
        "prompt": prompt,
        "n_predict": req.max_tokens or 512,
        "temperature": req.temperature or 0.7,
        "cache_prompt": True,
    }
    async with httpx.AsyncClient(timeout=LLAMA_TIMEOUT) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        text = data.get("content") or data.get("generated_text") or data.get("text") or ""
        if isinstance(text, list):
            text = "".join(text)
        return (text or "").strip(), "llama.cpp:completion"

async def _chat_via_llama(req: ChatReq) -> Tuple[str, str]:
    try:
        return await _chat_via_openai_compat(req)
    except FileNotFoundError:
        # 只有本地模式才允许回退到 /completion
        if USE_LEGACY_FALLBACK:
            return await _chat_via_legacy_completion(req)
        # 云端模式遇到 404 基本是 BASE 配置错误，直接抛出
        raise

# ------------------ HTTP 接口 ------------------
@app.post("/llm", response_model=ChatResp)
async def llm_endpoint(req: ChatReq, x_idempotency_key: Optional[str] = Header(None)):
    # 幂等缓存
    if x_idempotency_key:
        _gc_idem()
        cached = _IDEM.get(x_idempotency_key)
        if cached:
            return ChatResp(text=cached[1]["text"], model=cached[1]["model"], cached=True)

    try:
        text, model_used = await _chat_via_llama(req)
    except Exception as e:
        # 兜底（不抛 500），避免前端体验断裂
        text = f"[LLM 调用失败] {type(e).__name__}: {e}"
        model_used = "error"

    # 解析模型输出（JSON-ReAct）
    try:
        data = json.loads(text)
    except Exception:
        data = {}

    thought = data.get("thought", "")
    action = data.get("action", {})
    observation = data.get("observation", "")
    answer = data.get("answer", "好的")
    print(f"{thought=}, {action=}, {observation=}, {answer=}")

    if isinstance(action, dict) and action:
        function_name = action.get("name")
        args = action.get("args", {})
        try:
            # 你的工具注册表：function_map[函数名] -> 可调用对象
            if function_name in function_map:
                function_map[function_name](args)
            else:
                print(f"[Warn] unknown function: {function_name}")
        except Exception as e:
            # 捕获所有异常并打印
            print("[Error]", e)
            print(traceback.format_exc())

    out = {"text": answer, "model": model_used}
    if x_idempotency_key:
        _IDEM[x_idempotency_key] = (time.time(), out)
    return ChatResp(**out)

if __name__ == "__main__":
    # 启动参数不变
    uvicorn.run(app, host="127.0.0.1", port=8001, reload=False, workers=1)
