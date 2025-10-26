# === Word 写作工具 ===
import os
import re
import time

def _get_desktop_dir() -> str:
    return "C:\\Users\\gofor\\OneDrive\\Desktop"
    # return os.path.join(os.path.expandvars("%USERPROFILE%"), "Desktop")

def _safe_filename(name: str, default="Untitled") -> str:
    name = (name or "").strip()
    if not name:
        name = default
    # Windows 不能包含这些字符：\/:*?"<>|
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    return name

def _save_with_python_docx(full_path: str, content: str) -> str:
    try:
        from docx import Document
        from docx.shared import Pt
        doc = Document()
        # 简单样式（可根据需要微调）
        p = doc.add_paragraph(content or "")
        # p.style.font.name = 'Microsoft YaHei'  # 如需中文字体，可尝试设置
        # p.style.font.size = Pt(12)
        doc.save(full_path)
        return f"已写入并保存（python-docx）：{full_path}"
    except Exception as e:
        return f"python-docx 写入失败：{type(e).__name__}: {e}"

def _save_with_pywin32_word(full_path: str, content: str) -> str:
    try:
        import win32com.client as win32
        word = win32.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Add()
        # 写入内容
        selection = word.Selection
        selection.TypeText(content or "")
        # 保存为 docx
        doc.SaveAs(full_path)
        doc.Close(False)
        word.Quit()
        return f"已写入并保存（Word COM）：{full_path}"
    except Exception as e:
        return f"Word COM 写入失败：{type(e).__name__}: {e}"

def _save_as_txt(full_path_txt: str, content: str) -> str:
    try:
        with open(full_path_txt, "w", encoding="utf-8") as f:
            f.write(content or "")
        return f"已保存为纯文本：{full_path_txt}"
    except Exception as e:
        return f"保存 TXT 失败：{type(e).__name__}: {e}"

def write_article_in_word(file_name: str, content: str) -> str:
    """
    优先顺序：
    1) pywin32 调 Word 真写入（需安装 Office + pywin32）
    2) python-docx 直接生成 docx（无需 Office）
    3) 失败则降级写 txt
    """
    desktop = _get_desktop_dir()
    base = _safe_filename(file_name, default="我的文章")
    docx_path = os.path.join(desktop, base if base.lower().endswith(".docx") else base + ".docx")
    txt_path  = os.path.join(desktop, base if base.lower().endswith(".txt")  else base + ".txt")

    # 1) 尝试 Word COM
    try:
        import win32com.client  # noqa: F401
        msg = _save_with_pywin32_word(docx_path, content)
        # 若返回是失败信息，继续尝试 python-docx
        if "失败" not in msg:
            try:
                os.startfile(docx_path)
            except Exception:
                pass
            return msg
    except Exception:
        pass

    # 2) 尝试 python-docx
    try:
        import docx  # noqa: F401
        msg = _save_with_python_docx(docx_path, content)
        if "失败" not in msg:
            try:
                os.startfile(docx_path)
            except Exception:
                pass
            return msg
    except Exception:
        pass

    # 3) 最后降级为 txt
    msg = _save_as_txt(txt_path, content)
    try:
        os.startfile(txt_path)
    except Exception:
        pass
    return msg
