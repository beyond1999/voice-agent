# filename: voice_open_desktop_app.py
import os

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
    for root, _, files in os.walk("../shortcut"):
        for f in files:
            if keyword.lower() in f.lower() and f.lower().endswith(".lnk"):
                matches.append(os.path.join(root, f))
    if len(matches) == 0:
        print("No matches found")
        return []

    return matches[0] # 返回路径

def open_file(path: str):
    os.startfile(path)



