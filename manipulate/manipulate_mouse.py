# manipulate/mouse.py
from __future__ import annotations
import time
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import pyautogui

# ---- 日志配置（按需替换为你的项目日志系统）----
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


@dataclass
class MouseConfig:
    # 全局默认：动作间隔、失败重试、拖拽/移动默认时长等
    pause: float = 0.05               # 每次 PyAutoGUI 调用后自动等待
    duration_default: float = 0.15    # moveTo/dragTo 默认时长
    retries: int = 2                  # 失败重试次数
    retry_delay: float = 0.2          # 重试间隔
    fail_safe: bool = True            # 允许移动到左上角触发 FailSafe
    clamp_to_screen: bool = True      # 坐标越界时是否自动夹取到屏幕范围
    log_actions: bool = True          # 打印操作日志
    # 图像匹配（需要 opencv-python）
    image_confidence: float = 0.9     # locateOnScreen 置信度默认值
    image_grayscale: bool = False
    image_timeout: float = 5.0        # 等图像出现的默认超时（秒）


class MouseManipulator:
    def __init__(self, cfg: Optional[MouseConfig] = None):
        self.cfg = cfg or MouseConfig()
        pyautogui.PAUSE = self.cfg.pause
        pyautogui.FAILSAFE = self.cfg.fail_safe

    # ---------- 基础工具 ----------
    @staticmethod
    def screen_size() -> Tuple[int, int]:
        w, h = pyautogui.size()
        return int(w), int(h)

    @staticmethod
    def position() -> Tuple[int, int]:
        x, y = pyautogui.position()
        return int(x), int(y)

    def _clamp_xy(self, x: int, y: int) -> Tuple[int, int]:
        if not self.cfg.clamp_to_screen:
            return x, y
        w, h = self.screen_size()
        return max(0, min(x, w - 1)), max(0, min(y, h - 1))

    def _retry(self, fn, *args, **kwargs):
        last_exc = None
        for i in range(self.cfg.retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                last_exc = e
                if self.cfg.log_actions:
                    logger.warning(f"操作失败（第{i+1}次）：{e}")
                if i < self.cfg.retries:
                    time.sleep(self.cfg.retry_delay)
        raise last_exc

    # ---------- 鼠标移动/点击 ----------
    def move_to(self, x: int, y: int, duration: Optional[float] = None):
        x, y = self._clamp_xy(x, y)
        d = self.cfg.duration_default if duration is None else duration
        if self.cfg.log_actions:
            logger.info(f"move_to({x}, {y}, duration={d})")
        return self._retry(pyautogui.moveTo, x, y, duration=d)

    def click(self, x: Optional[int] = None, y: Optional[int] = None,
              clicks: int = 1, button: str = "left", interval: float = 0.1):
        if x is not None and y is not None:
            x, y = self._clamp_xy(x, y)
        if self.cfg.log_actions:
            logger.info(f"click(x={x}, y={y}, clicks={clicks}, button={button})")
        return self._retry(pyautogui.click, x=x, y=y, clicks=clicks, button=button, interval=interval)

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left"):
        return self.click(x, y, clicks=2, button=button, interval=0.05)

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None):
        return self.click(x, y, clicks=1, button="right")

    def scroll(self, amount: int):
        if self.cfg.log_actions:
            logger.info(f"scroll({amount})")
        return self._retry(pyautogui.scroll, amount)

    def drag_to(self, x: int, y: int, duration: Optional[float] = None, button: str = "left"):
        x, y = self._clamp_xy(x, y)
        d = self.cfg.duration_default if duration is None else duration
        if self.cfg.log_actions:
            logger.info(f"drag_to({x}, {y}, duration={d}, button={button})")
        return self._retry(pyautogui.dragTo, x, y, duration=d, button=button)

    # ---------- 键盘 ----------
    def key_down(self, key: str):
        if self.cfg.log_actions:
            logger.info(f"key_down({key})")
        return self._retry(pyautogui.keyDown, key)

    def key_up(self, key: str):
        if self.cfg.log_actions:
            logger.info(f"key_up({key})")
        return self._retry(pyautogui.keyUp, key)

    def press(self, key: str):
        if self.cfg.log_actions:
            logger.info(f"press({key})")
        return self._retry(pyautogui.press, key)

    def hotkey(self, *keys: str):
        if self.cfg.log_actions:
            logger.info(f"hotkey{keys}")
        return self._retry(pyautogui.hotkey, *keys)

    def type_text(self, text: str, interval: float = 0.02):
        if self.cfg.log_actions:
            logger.info(f"type_text({text!r})")
        return self._retry(pyautogui.typewrite, text, interval=interval)

    # ---------- 等待/图像定位（可选） ----------
    def wait(self, seconds: float):
        if self.cfg.log_actions:
            logger.info(f"wait({seconds})")
        time.sleep(seconds)

    def wait_for_image(self, image_path: str, timeout: Optional[float] = None,
                       confidence: Optional[float] = None, grayscale: Optional[bool] = None):
        """
        轮询直到屏幕上出现指定图片，返回其中心点坐标；需要安装 opencv-python。
        """
        _timeout = self.cfg.image_timeout if timeout is None else timeout
        _conf = self.cfg.image_confidence if confidence is None else confidence
        _gray = self.cfg.image_grayscale if grayscale is None else grayscale

        if self.cfg.log_actions:
            logger.info(f"wait_for_image('{image_path}', timeout={_timeout}, conf={_conf}, gray={_gray})")

        end = time.time() + _timeout
        last_box = None
        while time.time() < end:
            try:
                box = pyautogui.locateOnScreen(image_path, confidence=_conf, grayscale=_gray)
            except Exception as e:
                # 未安装 opencv 时会报错
                raise RuntimeError("locateOnScreen 需要安装 opencv-python（pip install opencv-python）") from e
            if box:
                last_box = box
                center = pyautogui.center(box)
                return int(center.x), int(center.y)
            time.sleep(0.15)
        raise TimeoutError(f"在 {_timeout}s 内未找到图像：{image_path}；最后匹配框：{last_box}")

    def click_image(self, image_path: str, timeout: Optional[float] = None,
                    confidence: Optional[float] = None, grayscale: Optional[bool] = None):
        x, y = self.wait_for_image(image_path, timeout, confidence, grayscale)
        return self.click(x, y)

# ---------------- 示例用法 ----------------
if __name__ == "__main__":
    mm = MouseManipulator(MouseConfig(pause=0.05, duration_default=0.2, retries=1))
    # 移动到(100, 200) 并单击
    mm.move_to(100, 200)
    mm.click()

    # 双击、右键、滚轮
    mm.double_click()
    mm.right_click()
    mm.scroll(120)

    # 拖拽到(800, 400)
    mm.drag_to(800, 400, duration=0.3)

    # Ctrl+S
    mm.key_down("ctrl")
    mm.press("s")
    mm.key_up("ctrl")

    # 或直接热键：
    # mm.hotkey("ctrl", "s")

    # 等待图像并点击（需要 opencv）
    # mm.click_image("images/play_button.png", timeout=5)
