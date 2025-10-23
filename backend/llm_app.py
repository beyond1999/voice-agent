from __future__ import annotations
import os
import time
import json
import traceback
import ast
from typing import List, Dict, Optional, Tuple

import httpx
import uvicorn
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 你的工具注册表（保持不变）
from function_call.function_call_register import function_map

# ================== 运行模式开关 ==================
# true/false/yes/1 皆可；默认云端
USE_LOCAL_MODEL = os.getenv("USE_LOCAL_MODEL", "false").lower() in ("1", "true", "yes")

# ================== 本地（llama.cpp 兼容） ==================
LOCAL_LLAMA_BASE_DEFAULT = "http://127.0.0.1:8003"
LOCAL_LLAMA_MODEL_DEFAULT = "qwen2.5-3b-instruct"
USE_LEGACY_FALLBACK = True  # 本地 404 时回退到 /completion

# ================== 云端（DeepSeek OpenAI 兼容） ==================
CLOUD_BASE_DEFAULT = "https://api.deepseek.com/v1"
CLOUD_MODEL_DEFAULT = "deepseek-chat"
CLOUD_AUTH_SCHEME_DEFAULT = "Bearer"
# 你说先写死 Key，就写在这里；也支持用环境变量覆盖
LLM_API_KEY = "sk-f415f1812d0b406792822e9cef183c6b" # os.getenv("LLM_API_KEY", "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx")
LLM_AUTH_SCHEME = os.getenv("LLM_AUTH_SCHEME", CLOUD_AUTH_SCHEME_DEFAULT)

# ================== 统一配置读取 ==================
LLAMA_BASE = os.getenv("LLAMA_BASE", LOCAL_LLAMA_BASE_DEFAULT if USE_LOCAL_MODEL else CLOUD_BASE_DEFAULT)
LLAMA_MODEL = os.getenv("LLAMA_MODEL", LOCAL_LLAMA_MODEL_DEFAULT if USE_LOCAL_MODEL else CLOUD_MODEL_DEFAULT)
LLAMA_TIMEOUT = float(os.getenv("LLAMA_TIMEOUT", "30"))

# ================== 幂等缓存 ==================
_IDEM: Dict[str, Tuple[float, Dict]] = {}
IDEM_TTL = 600.0

def _gc_idem():
    now = time.time()
    for k, (ts, _) in list(_IDEM.items()):
        if now - ts > IDEM_TTL:
            _IDEM.pop(k, None)

# ================== Pydantic ==================
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

# ================== FastAPI ==================
app = FastAPI(title="LLM Module (local/cloud switch)", version="0.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mode": "local" if USE_LOCAL_MODEL else "cloud",
        "llama_base": LLAMA_BASE,
        "llama_model": LLAMA_MODEL,
        "legacy_fallback": USE_LEGACY_FALLBACK if USE_LOCAL_MODEL else False,
        "api_key_present": bool(LLM_API_KEY) if not USE_LOCAL_MODEL else None,
    }

# ================== 调用适配 ==================
async def _chat_via_openai_compat(req: ChatReq) -> Tuple[str, str]:
    """
    兼容：本地 llama.cpp 或云端 DeepSeek 的 /v1/chat/completions
    """
    url = f"{LLAMA_BASE.rstrip('/')}/chat/completions" if LLAMA_BASE.endswith("/v1") else f"{LLAMA_BASE.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": LLAMA_MODEL,
        "messages": [m.model_dump() for m in req.messages],
        "temperature": req.temperature or 0.7,
        "max_tokens": req.max_tokens or 512,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if not USE_LOCAL_MODEL:
        headers["Authorization"] = f"{LLM_AUTH_SCHEME} {LLM_API_KEY}"

    async with httpx.AsyncClient(timeout=LLAMA_TIMEOUT) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code == 404 and USE_LOCAL_MODEL:
            raise FileNotFoundError("/v1/chat/completions not found (local)")
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
    if sys: parts.append(f"System: {sys}")
    for m in messages:
        if m.role == "user":
            parts.append(f"User: {m.content}")
        elif m.role == "assistant":
            parts.append(f"Assistant: {m.content}")
    parts.append("Assistant:")
    return "\n".join(parts)

async def _chat_via_legacy_completion(req: ChatReq) -> Tuple[str, str]:
    """
    llama.cpp 旧接口 /completion
    """
    url = f"{LLAMA_BASE.rstrip('/')}/completion"
    payload = {
        "prompt": _to_legacy_prompt(req.messages),
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
    """
    统一入口：
    - 云端：DeepSeek /v1/chat/completions
    - 本地：llama.cpp /v1/chat/completions；如 404 且允许回退，则 /completion
    """
    try:
        return await _chat_via_openai_compat(req)
    except FileNotFoundError:
        if USE_LOCAL_MODEL and USE_LEGACY_FALLBACK:
            return await _chat_via_legacy_completion(req)
        raise

# ================== HTTP 接口 ==================
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
        text = f"[LLM 调用失败] {type(e).__name__}: {e}"
        model_used = "error"

    # JSON-ReAct 解析（可选：模型若输出普通文本，这里会走 except）
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print("警告：LLM 输出不是标准 JSON，尝试使用 ast.literal_eval 进行修复...")
        try:
            # ast.literal_eval 可以安全地解析 Python 字面量 (如字典、列表)
            # 这是一个非常好的后备方案
            data = ast.literal_eval(text)
            if not isinstance(data, dict):
                print(f"修复失败：ast.literal_eval 解析结果不是字典，而是 {type(data).__name__}。")
                data = {} # 如果解析出来不是字典，也当作失败
        except (ValueError, SyntaxError) as e:
            # 如果两种方法都失败了，打印错误并继续
            print(f"错误：无法将 LLM 输出解析为 JSON 或 Python 字面量: {e}")
            data = {}
    except Exception as e:
        print(f"解析 LLM 输出时发生未知错误: {e}")
        data = {}

    thought = data.get("thought", "")
    action = data.get("action", {})
    observation = data.get("observation", "")
    answer = data.get("answer", text or "好的")
    print(f"{thought=}, {action=}, {observation=}, {answer=}")

    # 工具调用
    if isinstance(action, dict) and action:
        function_name = action.get("name")
        args = action.get("args", {})
        try:
            if function_name in function_map:
                function_map[function_name](**args)
            else:
                print(f"[Warn] unknown function: {function_name}")
        except Exception as e:
            print("[Error]", e)
            print(traceback.format_exc())

    out = {"text": answer, "model": model_used}
    if x_idempotency_key:
        _IDEM[x_idempotency_key] = (time.time(), out)
    return ChatResp(**out)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001, reload=False, workers=1)
