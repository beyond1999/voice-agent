import os
import time
import uuid
import json
import hashlib
import threading
from typing import List, Dict, Any, Optional

import requests
import speech_recognition as sr
import pyttsx3
from backend.prompt import SYSTEM_PROMPT

# ================== 配置 ==================
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:8001/llm")
LLM_MODEL = os.getenv("LLAMA_MODEL", "qwen2.5-3b-instruct")

# 语音识别参数
USE_GOOGLE = True        # True: Google Web Speech；False: 强制离线 Sphinx
LANG_CODE = "zh-CN"      # 识别语言（可改为 "en-US" 等）
PHRASE_TIME_LIMIT = 12   # 单次说话最长秒数
ENERGY_THRESHOLD = None  # None 表示自动；或设为 300~400 这样的固定阈值

# TTS 参数（pyttsx3 离线）
VOICE_NAME_CONTAINS = None   # 指定包含关键字的声音，如 "Chinese"；None 自动
TTS_RATE = 175               # 语速
TTS_VOLUME = 1.0             # 音量 0.0~1.0

# 幂等缓存 TTL（和你的后端一致 600s）
IDEM_TTL = 600.0


# ================== 简易幂等键 ==================
def make_idempotency_key(text: str, session_id: str) -> str:
    base = f"{session_id}:{text.strip()}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


# ================== LLM 客户端 ==================
class LLMClient:
    def __init__(self, endpoint: str, model: str):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.session_id = str(uuid.uuid4())
        self.messages: List[Dict[str, str]] = []
        self._last_sent: Dict[str, float] = {}  # idem_key -> ts

    def add_system(self, content: str):
        self.messages.append({"role": "system", "content": content})

    def add_user(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str):
        self.messages.append({"role": "assistant", "content": content})

    def _prune_idem(self):
        now = time.time()
        for k, ts in list(self._last_sent.items()):
            if now - ts > IDEM_TTL:
                self._last_sent.pop(k, None)

    def chat(self, temperature: float = 0.7, max_tokens: int = 512) -> str:
        payload = {
            "messages": self.messages,
            "session_id": self.session_id,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # 用最后一条 user 内容生成幂等键
        last_user = next((m["content"] for m in reversed(self.messages) if m["role"] == "user"), "")
        idem_key = make_idempotency_key(last_user, self.session_id)
        headers = {"x-idempotency-key": idem_key}

        self._prune_idem()
        self._last_sent[idem_key] = time.time()

        try:
            r = requests.post(self.endpoint, json=payload, headers=headers, timeout=60)
            r.raise_for_status()
            data = r.json()
            text = data.get("text", "").strip()
            return text
        except Exception as e:
            return f"[本地模型暂不可用] {type(e).__name__}: {e}"


# ================== TTS 播放器（pyttsx3） ==================
class TTS:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", TTS_RATE)
        self.engine.setProperty("volume", TTS_VOLUME)
        self._choose_voice(VOICE_NAME_CONTAINS)

        # 独立线程异步播报，避免阻塞主循环
        self._lock = threading.Lock()

    def _choose_voice(self, contains: Optional[str]):
        if contains:
            for v in self.engine.getProperty("voices"):
                name = getattr(v, "name", "") or ""
                if contains.lower() in name.lower():
                    self.engine.setProperty("voice", v.id)
                    break

    def say(self, text: str):
        if not text:
            return
        with self._lock:
            self.engine.say(text)
            self.engine.runAndWait()


# ================== 语音识别（speech_recognition） ==================
class ASR:
    def __init__(self, lang: str = "zh-CN", phrase_time_limit: int = 12, energy_threshold: Optional[int] = None):
        self.rec = sr.Recognizer()
        self.lang = lang
        self.phrase_time_limit = phrase_time_limit
        if energy_threshold is not None:
            self.rec.energy_threshold = energy_threshold
            self.rec.dynamic_energy_threshold = False
        else:
            self.rec.dynamic_energy_threshold = True  # 自动适配环境噪声

    def listen_once(self) -> Optional[str]:
        """按回车开始后调用；返回识别文本或 None"""
        with sr.Microphone() as mic:
            if self.rec.dynamic_energy_threshold:
                print(">>> 环境噪声校准中（1秒）…")
                self.rec.adjust_for_ambient_noise(mic, duration=1.0)
            print(f"🎙️ 开始说话（最长 {self.phrase_time_limit}s）…")
            audio = self.rec.listen(mic, timeout=None, phrase_time_limit=self.phrase_time_limit)
        # 优先 Google，失败则退回 Sphinx
        if USE_GOOGLE:
            try:
                text = self.rec.recognize_google(audio, language=self.lang)
                return text.strip()
            except Exception as e:
                print(f"[Google 识别失败，退回 Sphinx] {e}")
        # Sphinx（离线）
        try:
            text = self.rec.recognize_sphinx(audio, language=self.lang)
            return text.strip()
        except Exception as e:
            print(f"[Sphinx 识别失败] {e}")
            return None


# ================== 主循环 ==================


def main():
    print("== Voice Chat Client ==")
    print(f"- LLM endpoint: {LLM_ENDPOINT}")
    print("提示：按 Enter 说话，输入 q + Enter 退出。\n")

    llm = LLMClient(LLM_ENDPOINT, LLM_MODEL)
    llm.add_system(SYSTEM_PROMPT)

    tts = TTS()
    asr = ASR(lang=LANG_CODE, phrase_time_limit=PHRASE_TIME_LIMIT, energy_threshold=ENERGY_THRESHOLD)

    while True:
        cmd = input("按 Enter 开始说话（q 退出）> ").strip().lower()
        if cmd == "q":
            break

        user_text = asr.listen_once()
        if not user_text:
            print("（未识别到有效语音）\n")
            continue

        print(f"👤 你：{user_text}")
        llm.add_user(user_text)

        reply = llm.chat(temperature=0.2, max_tokens=512)
        llm.add_assistant(reply)
        print(f"🤖 助手：{reply}\n")

        # 语音播报
        tts.say(reply)

    print("Bye.")


if __name__ == "__main__":
    main()
