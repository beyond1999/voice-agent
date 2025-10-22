from manipulate.manipulate_app import *
from manipulate.manipulate_keyboard import qqmusic_hotkey_play_pause_v2
from manipulate.manipulate_mouse import *
def play_music(*args):
    # QQ音乐
    app_path = find_on_desktop("QQ音乐")
    if app_path:
        open_file(app_path)
        # press_space()
        time.sleep(1)
        qqmusic_hotkey_play_pause_v2()