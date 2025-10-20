# filename: voice_open_desktop_app.py
import os
import fnmatch
import time

import speech_recognition as sr
from manipulate_keyboard import play_pause,press_space, qqmusic_hotkey_play_pause_v2

def find_on_desktop(keyword: str):
    desktop = os.path.join(os.path.expandvars("%USERPROFILE%"), "Desktop")
    matches = []
    print(desktop)
    for root, _, files in os.walk(desktop):
        for f in files:
            if keyword.lower() in f.lower() and f.lower().endswith(".lnk"):
                matches.append(os.path.join(root, f))
    for root, _, files in os.walk("C:\\Users\\Public\\Desktop"):
        for f in files:
            if keyword.lower() in f.lower() and f.lower().endswith(".lnk"):
                matches.append(os.path.join(root, f))
    return matches

def open_file(path: str):
    os.startfile(path)

def listen_command():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎧 请说出你要打开的应用，例如：‘打开QQ音乐’")
        r.adjust_for_ambient_noise(source, duration=1)
        audio = r.listen(source)
        try:
            text = r.recognize_google(audio, language="zh-CN")
            print("🗣 识别结果：", text)
            return text
        except sr.UnknownValueError:
            print("❌ 没听清，请再试一次。")
        except sr.RequestError:
            print("⚠️ 无法连接到语音识别服务。")
    return ""

def extract_keyword(text: str):
    # 去掉常见命令前缀
    for prefix in ["打开", "启动", "运行", "开启", "打开一下", "启动一下"]:
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text.strip()

def main():
    text = listen_command()
    # text = "打开QQ音乐"
    if not text:
        return

    keyword = extract_keyword(text)
    print(f"🔍 搜索关键字：{keyword}")

    results = find_on_desktop(keyword)
    if not results:
        print("❌ 没找到匹配的桌面应用。")
        return

    # 自动打开第一个匹配
    target = results[0]
    print(f"✅ 找到并打开：{target}")
    open_file(target)
    # press_space()
    time.sleep(1)
    qqmusic_hotkey_play_pause_v2()

if __name__ == "__main__":
    main()
