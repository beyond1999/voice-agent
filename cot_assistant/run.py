# function_call/cot_assistant.py
from __future__ import annotations
from typing import Dict, Any
from chain_of_thought import CoTAssistant

def cot_assistant(goal: str) -> Dict[str, Any]:
    runner = CoTAssistant(goal=goal)
    result = runner.run()
    return result


result = cot_assistant("打开浏览器，搜索 B 站，输入 黑神话 并回车")
print(result["status"], result["final_note"])