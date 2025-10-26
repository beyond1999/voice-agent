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
from functools import partial

# —— 你现有的语音/LLM 模块（名字不同请按你的项目调整导入路径）——
from backend.voice_interact import LLMClient, ASR, TTS, SYSTEM_PROMPT, LLM_ENDPOINT, LLM_MODEL
# imports 顶部附近
import urllib.request, urllib.error  # 新增：轻量 HTTP 客户端（免第三方依赖）

# … 颜色定义处，新增一种“动作中的气泡”颜色
BUBBLE_ACTION = "#334155"  # Violet-500：执行过程/网关步骤
# 网关服务地址（可从环境变量覆盖）
GATEWAY_ENDPOINT = os.getenv("GATEWAY_ENDPOINT", "http://127.0.0.1:8077")

# —— 新增：持久化（SQLite）
from backend import persistence

APP_TITLE = "Voice Chat · Modern UI"
# 背景 (由深到浅，建立层次)
PRIMARY_BG = "#1e293b"     # Slate-800: 主背景
PANEL_BG   = "#334155"     # Slate-700: 面板/工具栏
BUBBLE_DARKGRAY  = "#3b4a63"     # Slate-600: AI气泡
BUBBLE_BLUE  = "#2563eb"     # Blue-600: 用户气泡
# BUBBLE_LIGHTGRAY = "#6b7a91"
BUBBLE_LIGHTGRAY = "#64748b"

# 文本
TEXT_MAIN  = "#e2e8f0"     # Slate-200: 主文本
TEXT_SUB   = "#94a3b8"     # Slate-400: 次要文本/提示

# 状态与交互
ACCENT     = "#22c55e"     # Green-500: 状态点/成功提示
DANGER     = "#dc2626"     # Red-600:   错误提示
WARN       = "#f59e0b"     # Amber-500: 警告 (如“聆听中”)
MUTED      = "#64748b"     # Slate-500: 次要元素

# 固定内容宽度（作为对齐参考线），以及蓝色气泡相对右边的留白
CONTENT_WIDTH = 960
USER_RIGHT_OFFSET = 60
BUBBLE_MAX_WIDTH = 600   # 蓝色/灰色气泡最大宽度（可按需调整）

def create_rounded_bubble(width, height, radius, color):
    """动态创建带圆角的矩形图片"""
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, width, height), radius, fill=color)
    return ImageTk.PhotoImage(image)

class ModernVoiceChat(tk.Tk):
    def __init__(self):
        super().__init__()

        self._suppress_auto_scroll = False  # 渲染中禁止 _add_bubble 自动滚动
        self._session_scroll = {}  # 记忆每个会话的滚动位置（0~1）

        self.title(APP_TITLE)
        self.geometry("1200x640")
        self.minsize(760, 520)
        self.configure(bg=PRIMARY_BG)
        self.font_main = ("Inter", 11, "normal")

        # ===== Persistence =====
        persistence.init_db()
        # 每次打开应用就新建一个会话
        _sessions = persistence.list_sessions()  # 已按 created_at DESC 排序
        self.current_sid = _sessions[0]["id"] if _sessions else persistence.create_session()

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
        self.history = []  # [{role, text, ts, type?}]

        # ===== Layout =====
        self._build_header()
        self._build_session_panel()   # 右侧会话列表
        self._build_chat_area()
        self._build_toolbar()
        self._build_input()

        # Key bindings
        self.bind("<Return>", self._enter_to_send)
        self.bind("<Shift-Return>", lambda e: None)  # just to avoid beep

        self._set_status("Ready")
        self._setup_input_context_menu()
        self.on_select_session(self.current_sid)



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

    def _build_session_panel(self):
        # 右侧固定宽度侧栏
        self.session_panel = tk.Frame(self, bg=PANEL_BG, width=260)
        self.session_panel.pack(side=tk.RIGHT, fill=tk.Y)

        # 顶部：新会话按钮
        top = tk.Frame(self.session_panel, bg=PANEL_BG, height=48)
        top.pack(side=tk.TOP, fill=tk.X)
        btn_new = self._mk_btn(top, "➕  New Session", self.on_new_session, solid=True)
        btn_new.pack(side=tk.LEFT, padx=10, pady=10)

        # 列表容器（可滚动）
        wrap = tk.Frame(self.session_panel, bg=PANEL_BG)
        wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.s_canvas = tk.Canvas(wrap, bg=PANEL_BG, highlightthickness=0)
        self.s_scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.s_canvas.yview)
        self.s_inner = tk.Frame(self.s_canvas, bg=PANEL_BG)

        self.s_inner.bind("<Configure>", lambda e: self.s_canvas.configure(scrollregion=self.s_canvas.bbox("all")))
        self.s_canvas.create_window((0, 0), window=self.s_inner, anchor="nw")
        self.s_canvas.configure(yscrollcommand=self.s_scroll.set)

        self.s_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.s_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._refresh_session_list()

    def _build_chat_area(self):
        wrap = tk.Frame(self, bg=PRIMARY_BG)
        wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(10, 8))

        # Scrollable canvas with inner frame for bubbles
        self.canvas = tk.Canvas(wrap, bg=PRIMARY_BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=PRIMARY_BG)

        # 绑定鼠标滚轮事件
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
        style.configure("Vertical.TScrollbar",
                        # width=8,
                        troughcolor=PANEL_BG, background=MUTED,
                        bordercolor=PANEL_BG, arrowcolor=TEXT_MAIN)

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

    def _build_input(self):
        wrap = tk.Frame(self, bg=PANEL_BG, height=120)
        wrap.pack(side=tk.BOTTOM, fill=tk.X, padx=18, pady=(10, 18))

        # 右侧容器（按钮和提示文字）
        right_panel = tk.Frame(wrap, bg=PANEL_BG)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)

        # Send 按钮
        self.send_btn = self._mk_btn(right_panel, "Send", self.on_send_text, solid=True)
        self.send_btn.pack(expand=True, fill='both')

        # 按键提示
        hint = tk.Label(right_panel, text="Shift+Enter: New line",
                        fg=TEXT_SUB, bg=PANEL_BG, font=("Consolas", 9))
        hint.pack(side=tk.BOTTOM, anchor="e", pady=(6, 0))

        # 文本输入框
        self.entry = tk.Text(wrap, height=4, wrap=tk.WORD, font=("Segoe UI", 11),
                             fg=TEXT_MAIN, bg="#0f172a", insertbackground=TEXT_MAIN,
                             relief=tk.FLAT, highlightthickness=2,
                             highlightbackground=PANEL_BG, highlightcolor=BUBBLE_BLUE)
        self.entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 8), pady=10)

        # 右键菜单
        self._setup_input_context_menu()

    # ---------------- UI helpers ----------------
    def _mk_btn(self, parent, text, cmd, solid=False):
        bg = BUBBLE_BLUE if solid else BUBBLE_DARKGRAY
        fg = "#ffffff"
        hover_bg = "#1d4ed8" if solid else "#64748b"

        f = tk.Frame(parent, bg=bg, cursor="hand2")
        lbl = tk.Label(f, text=text, fg=fg, bg=bg, font=("Segoe UI", 10, "bold"))
        lbl.pack(expand=True, fill='both', padx=12, pady=6)

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
        # Windows 和 macOS 使用 event.delta；Linux 使用 event.num
        try:
            if event.num == 5 or event.delta < 0:
                delta = 1
            else:
                delta = -1
        except Exception:
            delta = 1
        self.canvas.yview_scroll(delta, "units")

    # ---------------- Chat bubbles ----------------
    def _add_bubble(self, role: str, text: str, ts=None, msg_type: str = "normal"):
        ts = ts or time.strftime("%H:%M:%S")
        is_user = (role == "user")

        container = tk.Frame(self.inner, bg=PRIMARY_BG)
        container.pack(fill=tk.X, pady=5, padx=10)

        # Grid 权重：把内容挤到边缘
        if is_user:
            container.grid_columnconfigure(0, weight=1)
            container.grid_columnconfigure(1, weight=0)
        else:
            container.grid_columnconfigure(0, weight=0)
            container.grid_columnconfigure(1, weight=1)

        # wrapper 包裹 meta 和 bubble
        content_wrapper = tk.Frame(container, bg=PRIMARY_BG)
        content_wrapper.grid(row=0, column=1 if is_user else 0, sticky="e" if is_user else "w")

        meta = tk.Label(
            content_wrapper, text=("You" if is_user else "Assistant") + f" · {ts}",
            fg=TEXT_SUB, bg=PRIMARY_BG, font=("Segoe UI", 9)
        )
        meta.pack(anchor="e" if is_user else "w", padx=10, pady=(0, 3))

        # 配色
        if is_user:
            bubble_color = BUBBLE_LIGHTGRAY
            # bubble_color = BUBBLE_BLUE
            text_fg = "#ffffff"
            justify = tk.RIGHT
        else:
            if msg_type == "error":
                bubble_color = DANGER
            elif msg_type == "action":
                bubble_color = BUBBLE_ACTION  # <--- 新增：动作用色
            else:
                # bubble_color = BUBBLE_AI
                # bubble_color = "#0d9488"
                bubble_color = BUBBLE_BLUE
            text_fg = TEXT_MAIN

            justify = tk.LEFT

        # 先测量文本尺寸
        temp_lbl = tk.Label(
            content_wrapper, text=text, justify=justify, wraplength=600,
            font=("Segoe UI", 11), bg=PRIMARY_BG
        )
        self.update_idletasks()
        text_width = temp_lbl.winfo_reqwidth()
        text_height = temp_lbl.winfo_reqheight()
        temp_lbl.destroy()

        bubble_width = text_width + 30
        bubble_height = text_height + 20

        # 圆角图片缓存
        if not hasattr(self, '_bubble_image_cache'):
            self._bubble_image_cache = {}
        cache_key = (bubble_width, bubble_height, bubble_color)
        if cache_key in self._bubble_image_cache:
            bg_image = self._bubble_image_cache[cache_key]
        else:
            bg_image = create_rounded_bubble(bubble_width, bubble_height, 20, bubble_color)
            self._bubble_image_cache[cache_key] = bg_image

        # 最终气泡
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

        # 右键复制
        def show_context_menu(event):
            menu = tk.Menu(self, tearoff=0, bg=PANEL_BG, fg=TEXT_MAIN, activebackground=BUBBLE_DARKGRAY)
            menu.add_command(label="Copy Text", command=lambda: self.clipboard_clear() or self.clipboard_append(text))
            menu.tk_popup(event.x_root, event.y_root)

        bubble_lbl.bind("<Button-3>", show_context_menu)

        if not getattr(self, "_suppress_auto_scroll", False):
            self.after(50, lambda: self.canvas.yview_moveto(1.0))

    def _setup_input_context_menu(self):
        """为文本输入框创建右键菜单（剪切/复制/粘贴）"""
        self.input_menu = tk.Menu(self, tearoff=0, bg=PANEL_BG, fg=TEXT_MAIN)
        self.input_menu.add_command(label="Cut", command=lambda: self.focus_force() or self.entry.event_generate("<<Cut>>"))
        self.input_menu.add_command(label="Copy", command=lambda: self.focus_force() or self.entry.event_generate("<<Copy>>"))
        self.input_menu.add_command(label="Paste", command=lambda: self.focus_force() or self.entry.event_generate("<<Paste>>"))

        def show_menu(event):
            has_selection = self.entry.tag_ranges(tk.SEL)
            self.input_menu.entryconfig("Cut", state="normal" if has_selection else "disabled")
            self.input_menu.entryconfig("Copy", state="normal" if has_selection else "disabled")
            self.input_menu.tk_popup(event.x_root, event.y_root)

        self.entry.bind("<Button-3>", show_menu)

    # ---------------- Thread-safe UI ----------------
    def _ui(self, fn, *args, **kwargs):
        self.uiq.put((fn, args, kwargs))

    def _drain_uiq(self):
        try:
            while True:
                fn, args, kwargs = self.uiq.get_nowait()
                try:
                    fn(*args, **kwargs)
                except Exception as e:
                    print("[UI error]", type(e).__name__, e)
        except queue.Empty:
            pass
        finally:
            self.after(30, self._drain_uiq)

    # ---------------- Actions ----------------
    def _set_status(self, msg: str, mode: str = "idle"):
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
        # 网关调用：/gw <query>
        if text.startswith("/gw "):
            query = text[4:].strip()
            if not query:
                return
            self._append_user(text)  # 也把这条命令显示出来
            threading.Thread(target=self._gateway_round, args=(query,), daemon=True).start()
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
        # 持久化
        persistence.add_message(self.current_sid, "user", text, msg_type="normal")

    def _append_assistant(self, text: str, msg_type: str = "normal"):
        ts = time.strftime("%H:%M:%S")
        self.history.append({"role": "assistant", "text": text, "ts": ts, "type": msg_type})
        self._ui(self._add_bubble, "assistant", text, ts, msg_type)
        # 持久化（记录模型名）
        persistence.add_message(self.current_sid, "assistant", text, msg_type=msg_type, model=LLM_MODEL)

    def _append_action(self, text: str):
        """执行过程/工具步骤的可视化（紫色气泡），会落库 msg_type=action。"""
        ts = time.strftime("%H:%M:%S")
        self.history.append({"role": "assistant", "text": text, "ts": ts, "type": "action"})
        self._ui(self._add_bubble, "assistant", text, ts, "action")
        persistence.add_message(self.current_sid, "assistant", text, msg_type="action", model="gateway")

    def _llm_reply(self, user_text: str):
        try:
            self._set_status("Thinking…", "thinking")
            self.llm.add_user(user_text)
            reply = self.llm.chat(temperature=0.6, max_tokens=512)
            self.llm.add_assistant(reply)

            # UI & TTS 在主线程队列执行
            self._append_assistant(reply)
            if self.tts_enabled.get():
                self._ui(self.tts.say, reply)
            self._set_status("Ready", "idle")

        except Exception as e:
            error_msg = f"[Error] {type(e).__name__}: {e}"
            self._append_assistant(error_msg, msg_type="error")
            self._set_status("Error", mode="error")

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

    def _gateway_round(self, query: str):
        try:
            self._set_status("Gateway running…", "thinking")
            self._append_action("正在通过网关处理: " + query)

            payload = json.dumps({"query": query}).encode("utf-8")
            req = urllib.request.Request(
                GATEWAY_ENDPOINT.rstrip("/") + "/run",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            # 逐条步骤（动作态，紫色）
            for step in data.get("steps", []):
                self._append_action(step)

            # 最终回答（助手态，原色）
            final = data.get("answer", "(no answer)")
            self._append_assistant(final)
            self._set_status("Ready", "idle")

        except Exception as e:
            self._append_assistant(f"[Gateway Error] {type(e).__name__}: {e}", msg_type="error")
            self._set_status("Error", "error")

    # ---------------- Sessions (list/new/select/delete) ----------------
    def _refresh_session_list(self):
        # 清空现有子项
        for w in list(self.s_inner.children.values()):
            w.destroy()

        sessions = persistence.list_sessions()
        for s in sessions:
            sid = s["id"]
            title = s["title"]

            row = tk.Frame(self.s_inner, bg=PANEL_BG)
            row.pack(fill=tk.X, padx=8, pady=5)

            # 点击标题 = 切换会话
            title_btn = self._mk_btn(
                row, title,
                partial(self.on_select_session, sid),
                solid=False
            )
            title_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # 垃圾桶 = 删除会话
            trash_btn = self._mk_btn(
                row, "🗑",
                partial(self.on_delete_session, sid),
                solid=False
            )
            trash_btn.pack(side=tk.RIGHT, padx=(6, 0))

            # 高亮当前会话
            if sid == self.current_sid:
                for c in title_btn.winfo_children():
                    if isinstance(c, tk.Label):
                        c.config(fg="#ffffff", bg="#0ea5e9")
                title_btn.config(bg="#0ea5e9")

    def on_new_session(self):
        self.current_sid = persistence.create_session()
        self.on_clear()  # 清空界面
        self._set_status("New session created")
        self._refresh_session_list()

    def on_select_session(self, sid: str):
        # 1) 先保存当前会话的滚动位置（0~1）
        if hasattr(self, "current_sid") and self.current_sid:
            try:
                self._session_scroll[self.current_sid] = self.canvas.yview()[0]
            except Exception:
                pass

        # 2) 切换会话 & 关闭自动滚动
        self.current_sid = sid
        self._suppress_auto_scroll = True

        # 3) 清 UI 并加载消息
        for w in list(self.inner.children.values()):
            w.destroy()
        self.history.clear()
        msgs = persistence.get_messages(sid)
        for m in msgs:
            ts = m.get("ts", "")
            ts = ts[-8:] if ts and len(ts) >= 8 else time.strftime("%H:%M:%S")
            role = "user" if m["role"] == "user" else "assistant"
            msg_type = m.get("msg_type", "normal")
            self.history.append({"role": role, "text": m["content"], "ts": ts, "type": msg_type})
            self._add_bubble(role, m["content"], ts, msg_type)

        self._set_status("Session loaded")
        self._refresh_session_list()

        # 4) 强制刷新滚动区域
        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        # 5) 复位滚动条位置：
        #    - 优先恢复这个会话上次的位置
        #    - 否则默认看“最新消息”（底部）；如果内容很短，也能正常显示
        pos = self._session_scroll.get(sid, 1.0)
        try:
            self.canvas.yview_moveto(pos)
        except Exception:
            self.canvas.yview_moveto(0.0)  # 兜底：回到顶部

        # 6) 恢复自动滚动
        self._suppress_auto_scroll = False

    def on_delete_session(self, sid: str):
        if not messagebox.askyesno("Confirm delete", "确定删除该会话及其所有消息？此操作不可恢复。"):
            return
        persistence.delete_session(sid)
        # 若删的是当前会话，切到一个新会话
        if sid == self.current_sid:
            if len(persistence.list_sessions()) == 0:
                self.current_sid = persistence.create_session()
            else:
                self.current_sid = persistence.list_sessions()[0]
            self.on_clear()
        self._refresh_session_list()
        self._set_status("Session deleted")
        # 强制刷新滚动区域，使滚轮立即可用


if __name__ == "__main__":
    app = ModernVoiceChat()
    app.mainloop()
