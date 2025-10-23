# ===========================
# file: voice_gui_modern.py
# ===========================
import os
import time
import json
import queue
import threading
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
from tkinter import ttk, filedialog, messagebox

# —— 从你现有文件导入（若文件名不同请修改为你的模块名）——
from backend.voice_interact import LLMClient, ASR, TTS, SYSTEM_PROMPT, LLM_ENDPOINT, LLM_MODEL

APP_TITLE = "Voice Chat · Modern UI"
# 背景 (由深到浅，建立层次)
PRIMARY_BG = "#1e293b"     # Slate-800: 更柔和的深蓝灰，作为主背景
PANEL_BG   = "#334155"     # Slate-700: 面板/工具栏，比主背景稍亮，形成区隔
BUBBLE_AI  = "#475569"     # Slate-600: AI气泡，清晰地浮于主背景之上
BUBBLE_ME  = "#2563eb"     # Blue-600:  用户气泡，鲜明但不过于刺眼

# 文本
TEXT_MAIN  = "#e2e8f0"     # Slate-200: 主文本，清晰易读
TEXT_SUB   = "#94a3b8"     # Slate-400: 次要文本/提示

# 状态与交互
ACCENT     = "#22c55e"     # Green-500: 状态点/成功提示 (保持绿色)
DANGER     = "#dc2626"     # Red-600:   错误提示，颜色更饱和
WARN       = "#f59e0b"     # Amber-500: 警告 (如“聆听中”)
MUTED      = "#64748b"     # Slate-500: 禁用/滚动条等次要元素

def create_rounded_bubble(width, height, radius, color):
    """动态创建带圆角的矩形图片"""
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, width, height), radius, fill=color)
    return ImageTk.PhotoImage(image)

class ModernVoiceChat(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("920x640")
        self.minsize(760, 520)
        self.configure(bg=PRIMARY_BG)
        self.font_main = ("Inter", 11, "normal")

        # ===== Core =====
        self.llm = LLMClient(LLM_ENDPOINT, LLM_MODEL)
        self.llm.add_system(SYSTEM_PROMPT)
        self.asr = ASR()
        self.tts = TTS()

        self.tts_enabled = tk.BooleanVar(value=True)
        self.listening = tk.BooleanVar(value=False)

        # UI queue (thread-safe)
        self.uiq = queue.Queue()
        self.after(30, self._drain_uiq)

        # Chat history in memory
        self.history = []  # [{role, text, ts}]

        # ===== Layout =====
        self._build_header()
        self._build_chat_area()
        self._build_toolbar()
        self._build_input()

        # Key bindings
        self.bind("<Return>", self._enter_to_send)
        self.bind("<Shift-Return>", lambda e: None)  # just to avoid beep

        self._set_status("Ready")
        self._setup_input_context_menu()

    # ---------------- UI Builders ----------------
    def _build_header(self):
        header = tk.Frame(self, bg=PANEL_BG, height=56)
        header.pack(side=tk.TOP, fill=tk.X)

        self.status_dot = tk.Canvas(header, width=16, height=16, bg=PANEL_BG, highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, padx=(14, 8))
        self._draw_status_dot("idle")

        title = tk.Label(
            header, text=APP_TITLE, fg=TEXT_MAIN, bg=PANEL_BG,
            font=("Segoe UI", 14, "bold")
        )
        title.pack(side=tk.LEFT)

        self.header_status = tk.Label(
            header, text=f"Endpoint: {LLM_ENDPOINT} | Model: {LLM_MODEL}",
            fg=TEXT_SUB, bg=PANEL_BG, font=("Consolas", 10)
        )
        self.header_status.pack(side=tk.RIGHT, padx=14)

    def _build_chat_area(self):
        wrap = tk.Frame(self, bg=PRIMARY_BG)
        wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(10, 8))

        # Scrollable canvas with inner frame for bubbles
        self.canvas = tk.Canvas(wrap, bg=PRIMARY_BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=PRIMARY_BG)
                # --- 新增：绑定鼠标滚轮事件 ---
        # 我们需要绑定到 canvas 和 inner frame，确保鼠标在任何地方都能滚动
        self.canvas.bind("<Enter>", lambda _: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda _: self.canvas.unbind_all("<MouseWheel>"))
        self.inner.bind("<Enter>", lambda _: self.inner.bind_all("<MouseWheel>", self._on_mousewheel))
        self.inner.bind("<Leave>", lambda _: self.inner.unbind_all("<MouseWheel>"))

        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Style scrollbar
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Vertical.TScrollbar", width=8,troughcolor=PANEL_BG, background=MUTED, bordercolor=PANEL_BG, arrowcolor=TEXT_MAIN)

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=PANEL_BG, height=52)
        bar.pack(side=tk.TOP, fill=tk.X, padx=18)

        self.btn_speak = self._mk_btn(bar, "🎙  Speak", self.on_speak_toggle)
        self.btn_speak.pack(side=tk.LEFT, padx=(8, 6), pady=8)

        self.btn_tts = self._mk_toggle(bar, "▶  TTS", self.tts_enabled)
        self.btn_tts.pack(side=tk.LEFT, padx=6, pady=8)

        self._mk_divider(bar).pack(side=tk.LEFT, padx=6, pady=10)

        self.btn_clear = self._mk_btn(bar, "🧹  Clear", self.on_clear)
        self.btn_clear.pack(side=tk.LEFT, padx=6, pady=8)

        self.btn_save = self._mk_btn(bar, "💾  Export", self.on_export)
        self.btn_save.pack(side=tk.LEFT, padx=6, pady=8)

        self.toolbar_status = tk.Label(bar, text="",
                                       fg=TEXT_SUB, bg=PANEL_BG, font=("Consolas", 10))
        self.toolbar_status.pack(side=tk.RIGHT, padx=12)

# 在 ModernVoiceChat 类中
    def _build_input(self):
        wrap = tk.Frame(self, bg=PANEL_BG, height=120)
        wrap.pack(side=tk.BOTTOM, fill=tk.X, padx=18, pady=(10, 18))

        # --- 核心修复：完全使用 pack 布局，避免冲突 ---
        # 1. 创建右侧容器（按钮和提示文字），让它先靠右
        right_panel = tk.Frame(wrap, bg=PANEL_BG)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)

        # 2. 创建 Send 按钮，并将其放入右侧容器
        self.send_btn = self._mk_btn(right_panel, "Send", self.on_send_text, solid=True)
        self.send_btn.pack(expand=True, fill='both') # 按钮会填满 right_panel 的可用空间

        # 3. 创建提示文字，放在右侧容器的按钮下方
        hint = tk.Label(right_panel, text="Shift+Enter: New line",
                        fg=TEXT_SUB, bg=PANEL_BG, font=("Consolas", 9))
        hint.pack(side=tk.BOTTOM, anchor="e", pady=(6, 0))

        # 4. 创建文本输入框，它会自动填充剩下的所有空间
        self.entry = tk.Text(wrap, height=4, wrap=tk.WORD, font=("Segoe UI", 11),
                             fg=TEXT_MAIN, bg="#0f172a", insertbackground=TEXT_MAIN,
                             relief=tk.FLAT, highlightthickness=2,
                             highlightbackground=PANEL_BG, highlightcolor=BUBBLE_ME)
        self.entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 8), pady=10)

        # 别忘了设置右键菜单
        self._setup_input_context_menu()
    # ---------------- UI helpers ----------------


# 在 ModernVoiceChat 类中
    def _mk_btn(self, parent, text, cmd, solid=False):
        bg = BUBBLE_ME if solid else BUBBLE_AI
        fg = "#ffffff"
        hover_bg = "#1d4ed8" if solid else "#64748b"

        # Frame 本身是被它的父容器管理的（用 pack 或 grid）
        f = tk.Frame(parent, bg=bg, cursor="hand2")

        # --- 核心修复：内部统一使用 pack ---
        # Label 是 Frame 的子控件，我们用 pack 来管理它
        # expand=True 和 fill='both' 会让 Label 填满 Frame，其内部文本默认居中
        lbl = tk.Label(f, text=text, fg=fg, bg=bg, font=("Segoe UI", 10, "bold"))
        lbl.pack(expand=True, fill='both', padx=12, pady=6)

        # --- 事件绑定逻辑保持不变 ---
        def bind_all(widget, sequence, func):
            widget.bind(sequence, func)
            for child in widget.winfo_children():
                child.bind(sequence, func)

        def on_enter(e): f.config(bg=hover_bg); lbl.config(bg=bg)
        def on_leave(e): f.config(bg=bg); lbl.config(bg=bg)

        bind_all(f, "<Enter>", on_enter)
        bind_all(f, "<Leave>", on_leave)
        bind_all(f, "<Button-1>", lambda e: cmd())

        return f

    def _mk_toggle(self, parent, text, var: tk.BooleanVar):
        bg_on, bg_off = "#065f46", "#374151"
        fg = "#ffffff"
        f = tk.Frame(parent, bg=bg_on if var.get() else bg_off)
        lbl = tk.Label(f, text=text, fg=fg, bg=f["bg"], font=("Segoe UI", 10, "bold"), padx=12, pady=6, cursor="hand2")
        lbl.pack()
        def toggle(_=None):
            var.set(not var.get())
            f.configure(bg=bg_on if var.get() else bg_off)
            lbl.configure(bg=f["bg"])
        lbl.bind("<Button-1>", toggle)
        return f

    def _mk_divider(self, parent):
        return tk.Frame(parent, width=1, bg="#374151", height=28)

    def _draw_status_dot(self, mode: str):
        self.status_dot.delete("all")
        color = {"idle": MUTED, "thinking": ACCENT, "listening": WARN, "error": DANGER}.get(mode, MUTED)
        self.status_dot.create_oval(2, 2, 14, 14, fill=color, outline=color)

    def _enter_to_send(self, e):
        if e.state & 0x0001:   # Shift pressed
            return
        self.on_send_text()
        return "break"

    def _on_mousewheel(self, event):
            """处理鼠标滚轮事件，实现跨平台滚动"""
            # Windows 和 macOS 使用 event.delta
            # Linux 使用 event.num
            if event.num == 5 or event.delta < 0:
                delta = 1
            else:
                delta = -1
            self.canvas.yview_scroll(delta, "units")
    # ---------------- Chat bubbles ----------------
#    在 ModernVoiceChat 类中，使用这个最终版本的 _add_bubble
    def _add_bubble(self, role: str, text: str, ts=None, msg_type: str = "normal"):
        ts = ts or time.strftime("%H:%M:%S")
        is_user = (role == "user")

        container = tk.Frame(self.inner, bg=PRIMARY_BG)
        container.pack(fill=tk.X, pady=5, padx=10)

        # 正确的 Grid 权重，让空列伸展，把内容挤到边缘
        if is_user:
            container.grid_columnconfigure(0, weight=1)
            container.grid_columnconfigure(1, weight=0)
        else:
            container.grid_columnconfigure(0, weight=0)
            container.grid_columnconfigure(1, weight=1)

        # 使用一个 wrapper 来包裹 meta 和 bubble，确保它们是一个整体
        content_wrapper = tk.Frame(container, bg=PRIMARY_BG)
        content_wrapper.grid(row=0, column=1 if is_user else 0, sticky="e" if is_user else "w")

        meta = tk.Label(
            content_wrapper, text=("You" if is_user else "Assistant") + f" · {ts}",
            fg=TEXT_SUB, bg=PRIMARY_BG, font=("Segoe UI", 9)
        )
        meta.pack(anchor="e" if is_user else "w", padx=10, pady=(0, 3))

        # --- 统一使用 Label + 圆角图片背景，这是最可靠的方案 ---
        if is_user:
            bubble_color = BUBBLE_ME
            text_fg = "#ffffff"
            justify = tk.RIGHT
        else:
            bubble_color = DANGER if msg_type == "error" else BUBBLE_AI
            text_fg = TEXT_MAIN
            justify = tk.LEFT

        # 1. 使用临时 Label 计算尺寸
        temp_lbl = tk.Label(
            content_wrapper, text=text, justify=justify, wraplength=600,
            font=("Segoe UI", 11), bg=PRIMARY_BG
        )
        self.update_idletasks() # 确保尺寸计算准确
        text_width = temp_lbl.winfo_reqwidth()
        text_height = temp_lbl.winfo_reqheight()
        temp_lbl.destroy()
        
        bubble_width = text_width + 30
        bubble_height = text_height + 20
        
        # 2. 创建圆角背景图片
        bg_image = create_rounded_bubble(bubble_width, bubble_height, 20, bubble_color)
        if not hasattr(self, '_bubble_images'): self._bubble_images = []
        self._bubble_images.append(bg_image)

        # 3. 创建最终的气泡 Label
        bubble_lbl = tk.Label(
            content_wrapper,
            text=text,
            image=bg_image,
            compound="center",
            justify=justify,
            wraplength=600,
            fg=text_fg,
            font=("Segoe UI", 11),
            bd=0, highlightthickness=0, bg=PRIMARY_BG
        )
        bubble_lbl.pack(anchor="e" if is_user else "w")

        # --- 为所有气泡添加右键复制功能 ---
        def show_context_menu(event):
            menu = tk.Menu(self, tearoff=0, bg=PANEL_BG, fg=TEXT_MAIN, activebackground=BUBBLE_AI)
            menu.add_command(label="Copy Text", command=lambda: self.clipboard_clear() or self.clipboard_append(text))
            menu.tk_popup(event.x_root, event.y_root)

        bubble_lbl.bind("<Button-3>", show_context_menu)

        self.after(50, lambda: self.canvas.yview_moveto(1.0))
    # 在 ModernVoiceChat 类中，添加这个新方法
    def _setup_input_context_menu(self):
        """为文本输入框创建右键菜单（剪切/复制/粘贴）"""
        self.input_menu = tk.Menu(self, tearoff=0, bg=PANEL_BG, fg=TEXT_MAIN)
        self.input_menu.add_command(label="Cut", command=lambda: self.focus_force() or self.entry.event_generate("<<Cut>>"))
        self.input_menu.add_command(label="Copy", command=lambda: self.focus_force() or self.entry.event_generate("<<Copy>>"))
        self.input_menu.add_command(label="Paste", command=lambda: self.focus_force() or self.entry.event_generate("<<Paste>>"))

        def show_menu(event):
            # 禁用/启用 Cut 和 Copy 选项
            has_selection = self.entry.tag_ranges(tk.SEL)
            if has_selection:
                self.input_menu.entryconfig("Cut", state="normal")
                self.input_menu.entryconfig("Copy", state="normal")
            else:
                self.input_menu.entryconfig("Cut", state="disabled")
                self.input_menu.entryconfig("Copy", state="disabled")
            
            self.input_menu.tk_popup(event.x_root, event.y_root)

        self.entry.bind("<Button-3>", show_menu)

    # ---------------- Thread-safe UI ----------------
    # 修复点①：支持 kwargs，避免 unknown option 错误
    def _ui(self, fn, *args, **kwargs):
        self.uiq.put((fn, args, kwargs))

    def _drain_uiq(self):
        try:
            while True:
                fn, args, kwargs = self.uiq.get_nowait()
                try:
                    fn(*args, **kwargs)
                except Exception as e:
                    # 打印 UI 回调异常，便于排查
                    print("[UI error]", type(e).__name__, e)
        except queue.Empty:
            pass
        finally:
            self.after(30, self._drain_uiq)

    # ---------------- Actions ----------------
    def _set_status(self, msg: str, mode: str = "idle"):
        # 修复点②：用关键字参数 text=... 更新 Label 文本
        self._ui(
            self.header_status.configure,
            text=f"Endpoint: {LLM_ENDPOINT} | Model: {LLM_MODEL}  ·  {msg}"
        )
        self._ui(self._draw_status_dot, mode)
        self._ui(self.toolbar_status.configure, text=msg)

    def on_clear(self):
        for w in list(self.inner.children.values()):
            w.destroy()
        self.history.clear()
        self._set_status("Cleared.")

    def on_export(self):
        if not self.history:
            messagebox.showinfo("Export", "Chat is empty.")
            return
        save = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")], title="Export chat history"
        )
        if not save:
            return
        try:
            with open(save, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            self._set_status(f"Saved to {os.path.basename(save)}")
        except Exception as e:
            messagebox.showerror("Export error", str(e))
            self._set_status("Export error", mode="error")

    def on_send_text(self):
        text = self.entry.get("1.0", tk.END).strip()
        if not text:
            return
        self.entry.delete("1.0", tk.END)
        self._append_user(text)
        threading.Thread(target=self._llm_reply, args=(text,), daemon=True).start()

    def on_speak_toggle(self):
        if self.listening.get():
            self.listening.set(False)
            self._set_status("Stopped.", "idle")
            return
        self.listening.set(True)
        self._set_status("Listening…", "listening")
        threading.Thread(target=self._once_asr_round, daemon=True).start()

    # ---------------- Logic ----------------
    def _append_user(self, text: str):
        ts = time.strftime("%H:%M:%S")
        self.history.append({"role": "user", "text": text, "ts": ts})
        self._ui(self._add_bubble, "user", text, ts)

    def _append_assistant(self, text: str):
        ts = time.strftime("%H:%M:%S")
        self.history.append({"role": "assistant", "text": text, "ts": ts})
        self._ui(self._add_bubble, "assistant", text, ts)

    def _llm_reply(self, user_text: str):
        try:
            self._set_status("Thinking…", "thinking")
            self.llm.add_user(user_text)
            reply = self.llm.chat(temperature=0.6, max_tokens=512)
            self.llm.add_assistant(reply)
            self._append_assistant(reply)
            if self.tts_enabled.get():
                self.tts.say(reply)
            self._set_status("Ready", "idle")
        except Exception as e:
            self._append_assistant(f"[Error] {type(e).__name__}: {e}")
            self._set_status("Error", "error")

    def _once_asr_round(self):
        try:
            user_text = self.asr.listen_once()
            self.listening.set(False)
            if not user_text:
                self._set_status("No speech detected", "idle")
                self._append_assistant("（未识别到有效语音）")
                return
            self._append_user(user_text)
            self._llm_reply(user_text)
        except Exception as e:
            self.listening.set(False)
            self._append_assistant(f"[ASR Error] {type(e).__name__}: {e}")
            self._set_status("ASR Error", "error")

if __name__ == "__main__":
    app = ModernVoiceChat()
    app.mainloop()
