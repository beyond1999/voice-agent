# filename: qqmusic_control.py
import time
import os
import ctypes
import sys
import pyautogui
import pygetwindow as gw
import keyboard
# 可选依赖，用于激活窗口与键鼠操作（pip install pyautogui pygetwindow keyboard）
# try:
#     import pyautogui
#     import pygetwindow as gw
#     import keyboard
# except Exception:
#     print("pyautogui not installed")
#     pyautogui = None
#     gw = None
#     keyboard = None

# ========== 方案A：系统媒体键（不需要前台） ==========
# 使用 Win32 SendInput 发送媒体键（更稳，QQ音乐、Spotify、系统播放器都吃）
# 参考 VK_ 定义
VK_MEDIA_NEXT_TRACK   = 0xB0
VK_MEDIA_PREV_TRACK   = 0xB1
VK_MEDIA_PLAY_PAUSE   = 0xB3
VK_VOLUME_MUTE        = 0xAD
VK_VOLUME_DOWN        = 0xAE
VK_VOLUME_UP          = 0xAF

# INPUT 结构体定义（简版）
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ki", KEYBDINPUT)]

SendInput = ctypes.windll.user32.SendInput

def press_vk(vk):
    # 按下
    inp = INPUT(type=1, ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0, dwExtraInfo=None))
    # 抬起
    inp_up = INPUT(type=1, ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=2, time=0, dwExtraInfo=None))
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
    time.sleep(0.02)
    SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up))

def play_pause():
    press_vk(VK_MEDIA_PLAY_PAUSE)

def next_track():
    press_vk(VK_MEDIA_NEXT_TRACK)

def prev_track():
    press_vk(VK_MEDIA_PREV_TRACK)

def vol_up():
    press_vk(VK_VOLUME_UP)

def vol_down():
    press_vk(VK_VOLUME_DOWN)

def vol_mute():
    press_vk(VK_VOLUME_MUTE)

# ========== 方案B：激活 QQ 音乐并用快捷键（需要前台） ==========
QQMUSIC_EXE = r"C:\Program Files (x86)\Tencent\QQMusic\QQMusic.exe"  # 按你机器实际路径改
QQMUSIC_TITLE_KEYWORD = "QQ音乐"

def ensure_qqmusic_front():
    """如果没启动则启动；找到窗口并激活。"""
    if gw is None or pyautogui is None or keyboard is None:
        print("（提示）未安装 pyautogui/pygetwindow/keyboard，跳过前台激活方案。")
        return False
    # 已有窗口？
    wins = gw.getWindowsWithTitle(QQMUSIC_TITLE_KEYWORD)
    if not wins:
        if os.path.exists(QQMUSIC_EXE):
            os.startfile(QQMUSIC_EXE)
            time.sleep(5)
            wins = gw.getWindowsWithTitle(QQMUSIC_TITLE_KEYWORD)
        else:
            print("未找到 QQ 音乐路径，请检查 QQMUSIC_EXE。")
            return False
    if not wins:
        print("未找到 QQ 音乐窗口。")
        return False
    win = wins[0]
    try:
        win.activate()
        time.sleep(0.5)
        return True
    except Exception as e:
        print("激活窗口失败：", e)
        return False

def qqmusic_hotkey_play_pause():
    """Ctrl+Alt+P 播放/暂停"""
    if keyboard:
        keyboard.press_and_release('ctrl+alt+p')
def qqmusic_hotkey_play_pause_v2():
    """Ctrl+Alt+P 播放/暂停"""
    if keyboard:
        keyboard.press_and_release('ctrl+alt+f5')

def qqmusic_hotkey_next():
    if keyboard:
        keyboard.press_and_release('ctrl+alt+right')

def qqmusic_hotkey_prev():
    if keyboard:
        keyboard.press_and_release('ctrl+alt+left')
def press_space():
    if keyboard:
        keyboard.press_and_release('space')

# ========== 命令入口 ==========
USAGE = """
用法：
play       # 播放/暂停（优先媒体键）
next       # 下一首
prev       # 上一首
volup      # 音量+
voldown    # 音量-
mute       # 静音
frontplay  # 激活QQ音乐窗口后用快捷键播放/暂停
"""

if __name__ == "__main__":
    print(USAGE)
    cmd = input("请输入命令， help输出菜单")
    while cmd != "exit":
        if cmd == "play":
            play_pause()
        elif cmd == "next":
            next_track()
        elif cmd == "prev":
            prev_track()
        elif cmd == "volup":
            vol_up()
        elif cmd == "voldown":
            vol_down()
        elif cmd == "mute":
            vol_mute()
        elif cmd == "frontplay":
            if ensure_qqmusic_front():
                qqmusic_hotkey_play_pause()
        else:
            print(USAGE)
