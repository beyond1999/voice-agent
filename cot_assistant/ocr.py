from __future__ import annotations
from typing import List, Dict
from pytesseract import Output
from PIL import Image
import pytesseract
import os

# 常见安装路径（自动检测）
COMMON_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe".format(os.getenv("USERNAME", "")),
]

for path in COMMON_PATHS:
    if os.path.exists(path):
        pytesseract.pytesseract.tesseract_cmd = path
        break
else:
    raise FileNotFoundError("未找到 Tesseract，请检查是否安装或手动指定路径。")

class OCR:
    def read(self, pil_img: Image.Image) -> List[Dict]:
        data = pytesseract.image_to_data(pil_img, lang="chi_sim+eng", output_type=Output.DICT)
        result = []
        n = len(data["text"])
        for i in range(n):
            txt = (data["text"][i] or "").strip()
            try:
                conf = float(data["conf"][i])
            except Exception:
                conf = -1.0
            if txt and conf >= 60:
                box = (int(data["left"][i]), int(data["top"][i]),
                       int(data["width"][i]), int(data["height"][i]))
                result.append({"text": txt, "conf": conf, "box": box})
        return result
