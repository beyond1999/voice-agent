from __future__ import annotations

def build_cot_prompt(goal: str, step_idx: int, ocr_items: list[dict], history_hint: str = "") -> str:
    # 控制摘要长度，避免太长
    top = ocr_items[:30]
    ocr_summary = [
        f'{i+1}. "{it["text"]}" conf={int(it["conf"])} box={it["box"]}'
        for i, it in enumerate(top)
    ]
    ocr_summary_str = "\n".join(ocr_summary)

    return f"""
你是一个“执行助手（CoT Assistant）”。目标：{goal}
你需要按步骤执行，每步只输出一个严格的 JSON 动作对象，不要多说一句话。

观察（Step {step_idx}）：
屏幕可见文本（Top {len(top)}）：
{ocr_summary_str}

历史提示：{history_hint}

请输出 JSON（RFC8259）：
{{
  "thought": "你下一步要做什么（简短）",
  "action": {{
     "op": "click" | "double_click" | "type" | "hotkey" | "scroll" | "wait" | "finish",
     "selector": {{"by":"text"|"image"|"coords","value":"..."}},   // 某些动作可为 null
     "text": "...",         // 当 op=type/hotkey 需要
     "enter": false,        // type 后是否回车
     "amount": 0,           // scroll 用
     "seconds": 0.0,        // wait 用
     "timeout": 5.0
  }}
}}
只输出 JSON。
"""
