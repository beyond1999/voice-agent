from __future__ import annotations
import json, time
from typing import Optional, Dict, Any, Tuple

from schemas import Action, Selector
from cot_prompt import build_cot_prompt
from vision import Screen
from ocr import OCR
from manipulate.manipulate_mouse import MouseManipulator, MouseConfig

# 你已有的 LLM 客户端：请封装一个 predict_json(messages or prompt)->dict
class CoTLLMClient:
    def __init__(self, chat_endpoint: str = "http://127.0.0.1:8001/llm", model: str = "qwen2.5-7b-cot"):
        self.endpoint = chat_endpoint
        self.model = model

    def predict_json(self, prompt: str) -> Dict[str, Any]:
        # 你已有后端可接 OpenAI 兼容；这里用 messages 形式更稳
        import httpx
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "只返回严格 JSON，符合 RFC8259。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
        }
        r = httpx.post(self.endpoint, json=payload, timeout=60)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        # 尝试解析 JSON（防御）
        try:
            return json.loads(content)
        except Exception:
            # 简单提取 {...} 片段
            s = content.find("{"); e = content.rfind("}")
            return json.loads(content[s:e+1])

class CoTAssistant:
    def __init__(self, goal: str,
                 llm: Optional[CoTLLMClient] = None,
                 mouse: Optional[MouseManipulator] = None,
                 max_steps: int = 12):
        self.goal = goal
        self.llm = llm or CoTLLMClient()
        self.mouse = mouse or MouseManipulator(MouseConfig())
        self.screen = Screen()
        self.ocr = OCR()
        self.max_steps = max_steps
        self.trace = []

    # ========== Public入口 ==========
    def run(self) -> Dict[str, Any]:
        for step in range(self.max_steps):
            img = self.screen.capture_full()
            ocr_items = self.ocr.read(img)

            prompt = build_cot_prompt(self.goal, step, ocr_items, history_hint=self._history_hint())
            resp = self.llm.predict_json(prompt)

            act = Action.model_validate(resp.get("action"))
            self.trace.append({"step": step, "thought": resp.get("thought", ""), "action": act.model_dump()})

            result = self._execute(act, ocr_items)
            self.trace[-1]["result"] = result

            if act.op == "finish" or result.get("done"):
                return {"status": "success", "final_note": result.get("note", "完成"), "trace": self.trace}

        return {"status": "timeout", "final_note": "达到最大步数仍未完成", "trace": self.trace}

    # ========== 执行 ==========
    def _execute(self, act: Action, ocr_items: list[dict]) -> Dict[str, Any]:
        try:
            if act.op in ("click", "double_click"):
                x, y = self._resolve_selector(act.selector, ocr_items, act.timeout)
                if act.op == "click":
                    self.mouse.click(x, y)
                else:
                    self.mouse.double_click(x, y)
                return {"ok": True}
            elif act.op == "type":
                self.mouse.type_text(act.text or "")
                if act.enter:
                    self.mouse.press("enter")
                return {"ok": True}
            elif act.op == "hotkey":
                # hotkey 文本如 "ctrl+f" or "ctrl+alt+p"
                keys = (act.text or "").split("+")
                keys = [k.strip() for k in keys if k.strip()]
                if not keys:
                    return {"ok": False, "note": "hotkey 需要 text"}
                self.mouse.hotkey(*keys)
                return {"ok": True}
            elif act.op == "scroll":
                self.mouse.scroll(int(act.amount))
                return {"ok": True}
            elif act.op == "wait":
                self.mouse.wait(float(act.seconds or 0.5))
                return {"ok": True}
            elif act.op == "finish":
                return {"ok": True, "done": True, "note": "执行体主动结束"}
            else:
                return {"ok": False, "note": f"未知操作: {act.op}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ========== 选择器解析 ==========
    def _resolve_selector(self, sel: Selector, ocr_items: list[dict], timeout: float) -> Tuple[int, int]:
        if sel.by == "coords":
            x, y = sel.value  # type: ignore
            return int(x), int(y)
        end = time.time() + float(timeout or 5.0)
        while time.time() < end:
            if sel.by == "text":
                pos = self._find_by_text(ocr_items, str(sel.value))
                if pos:
                    return pos
            elif sel.by == "image":
                # TODO: 模板匹配；占位，先抛错
                raise RuntimeError("image selector 未实现（后续用 OpenCV 模板匹配）")
            # 重刷OCR（UI动态变化）
            ocr_items = self.ocr.read(self.screen.capture_full())
            time.sleep(0.2)
        raise TimeoutError(f"在 {timeout}s 内未匹配到 selector: {sel.model_dump()}")

    def _find_by_text(self, ocr_items: list[dict], keyword: str) -> Optional[Tuple[int, int]]:
        keyword = keyword.strip().lower()
        best = None
        for it in ocr_items:
            t = it["text"].strip().lower()
            if keyword in t:
                l, top, w, h = it["box"]
                center = (l + w // 2, top + h // 2)
                score = (it["conf"], -abs(len(t) - len(keyword)))
                if best is None or score > best[0]:
                    best = (score, center)
        return best[1] if best else None

    # ========== 提示历史（可选，用于提示 CoT 上文）==========
    def _history_hint(self) -> str:
        # 只给很短的历史摘要，防止提示累积
        last2 = self.trace[-2:] if len(self.trace) >= 2 else self.trace
        return "; ".join([f's{t["step"]}:{t["action"]["op"]}' for t in last2])
