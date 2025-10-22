import pyautogui, time

def test_mouse():
    # 移动到(100, 200)
    pyautogui.moveTo(100, 200, duration=0.2)

    # 左键单击 / 双击 / 右键
    pyautogui.click()
    pyautogui.doubleClick()
    pyautogui.rightClick()

    # 滚轮（向上120单位）
    pyautogui.scroll(120)

    # 拖拽（把鼠标从当前点拖到 800, 400）
    pyautogui.dragTo(800, 400, duration=0.3, button='left')

    # 按下/抬起某个键
    pyautogui.keyDown('ctrl')
    pyautogui.press('s')
    pyautogui.keyUp('ctrl')
