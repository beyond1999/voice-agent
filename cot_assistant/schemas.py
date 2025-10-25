from __future__ import annotations
from pydantic import BaseModel, Field, model_validator
from typing import Literal, Optional, Tuple, Union

class Selector(BaseModel):
    by: Literal["text", "image", "coords"] = Field(..., description="定位方式")
    value: Union[str, Tuple[int, int]] = Field(..., description="文本/模板路径/(x,y)")

class Action(BaseModel):
    op: Literal["click", "double_click", "type", "hotkey", "scroll", "wait", "finish"]
    selector: Optional[Selector] = None
    text: Optional[str] = None       # type/hotkey 用
    enter: bool = False              # type 后是否回车
    amount: int = 0                  # scroll 步进
    seconds: float = 0.0             # wait 秒
    timeout: float = 5.0

    @model_validator(mode="after")
    def _check(self):
        if self.op in ("click", "double_click") and self.selector is None:
            raise ValueError("click/double_click 需要 selector")
        if self.op == "type" and self.text is None:
            raise ValueError("type 需要 text")
        return self
