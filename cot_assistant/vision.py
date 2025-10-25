from __future__ import annotations
import mss
import numpy as np
from PIL import Image



class Screen:
    def capture_full(self):
        with mss.mss() as sct:
            raw = sct.grab(sct.monitors[0])
            img = np.array(raw)[:, :, :3]
        return Image.fromarray(img)

    def size(self):
        with mss.mss() as sct:
            mon = sct.monitors[0]
            return mon["width"], mon["height"]


