# ===========================
# file: voice_gui_modern.py
# ===========================
import os
import time
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# —— 从你现有文件导入（若文件名不同请修改为你的模块名）——
from backend.voice_interact import LLMClient, ASR, TTS, SYSTEM_PROMPT, LLM_ENDPOINT, LLM_MODEL

APP_TITLE = "Voice Chat · Modern UI"
PRIMARY_BG = "#0f172a"     # slate-900
PANEL_BG   = "#111827"     # gray-900
BUBBLE_AI  = "#1f2937"     # gray-800
BUBBLE_ME  = "#1d4ed8"     # blue-600
TEXT_MAIN  = "#e5e7eb"     # gray-200
TEXT_SUB   = "#9ca3af"     # gray-400
ACCENT     = "#22c55e"     # green-500
DANGER     = "#ef4444"     # red-500
WARN       = "#f59e0b"     # amber-500
MUTED      = "#6b7280"     # gray-500

class ModernVoiceChat(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("920x640")
        self.minsize(760, 520)
        self.configure(bg=PRIMARY_BG)

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

        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Style scrollbar
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Vertical.TScrollbar", troughcolor=PANEL_BG, background=MUTED, bordercolor=PANEL_BG, arrowcolor=TEXT_MAIN)

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=PANEL_BG, height=48)
        bar.pack(side=tk.TOP, fill=tk.X, padx=12)

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
        wrap.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=12)

        self.entry = tk.Text(wrap, height=4, wrap=tk.WORD, font=("Segoe UI", 11),
                             fg=TEXT_MAIN, bg="#0b1222", insertbackground=TEXT_MAIN, relief=tk.FLAT)
        self.entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 8), pady=10)

        self.send_btn = self._mk_btn(wrap, "Send", self.on_send_text, solid=True)
        self.send_btn.pack(side=tk.LEFT, padx=(0, 10), pady=10, ipadx=14, ipady=6)

        hint = tk.Label(wrap, text="Enter: Send   ·   Shift+Enter: New line",
                        fg=TEXT_SUB, bg=PANEL_BG, font=("Consolas", 9))
        hint.pack(side=tk.BOTTOM, anchor="e", padx=12, pady=(0, 6))

    # ---------------- UI helpers ----------------
    def _mk_btn(self, parent, text, cmd, solid=False):
        bg = "#1f2937" if not solid else "#2563eb"
        fg = TEXT_MAIN if not solid else "#ffffff"
        hover = "#374151" if not solid else "#1d4ed8"

        f = tk.Frame(parent, bg=bg)
        lbl = tk.Label(f, text=text, fg=fg, bg=bg, font=("Segoe UI", 10, "bold"), padx=12, pady=6, cursor="hand2")
        lbl.pack()
        def on_enter(e): lbl.configure(bg=hover)
        def on_leave(e): lbl.configure(bg=bg)
        def on_click(e): cmd()
        lbl.bind("<Enter>", on_enter)
        lbl.bind("<Leave>", on_leave)
        lbl.bind("<Button-1>", on_click)
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

    # ---------------- Chat bubbles ----------------
    def _add_bubble(self, role: str, text: str, ts=None):
        ts = ts or time.strftime("%H:%M:%S")
        is_user = (role == "user")
        container = tk.Frame(self.inner, bg=PRIMARY_BG)
        container.pack(fill=tk.X, pady=4, padx=6, anchor="e" if is_user else "w")

        # name + time
        meta = tk.Label(
            container,
            text=("You" if is_user else "Assistant") + f"  ·  {ts}",
            fg=TEXT_SUB, bg=PRIMARY_BG, font=("Segoe UI", 9)
        )
        meta.pack(anchor="e" if is_user else "w", padx=(2, 2))

        wrap = tk.Frame(container, bg=PRIMARY_BG)
        wrap.pack(anchor="e" if is_user else "w")

        bubble = tk.Frame(
            wrap, bg=BUBBLE_ME if is_user else BUBBLE_AI,
            padx=12, pady=8
        )
        bubble.pack(anchor="e" if is_user else "w")

        lbl = tk.Label(
            bubble, text=text, justify=tk.LEFT, wraplength=720,
            fg="#ffffff" if is_user else TEXT_MAIN,
            bg=bubble["bg"], font=("Segoe UI", 11)
        )
        lbl.pack()

        self.after(50, lambda: self.canvas.yview_moveto(1.0))

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
