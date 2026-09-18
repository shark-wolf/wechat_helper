import time
import random
import ctypes
import win32gui
import win32con
import win32process
import win32api
import pyperclip
import pywinauto.keyboard as keyboard
from config import SAFETY_CONFIG

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def human_delay(min_s=None, max_s=None):
    low = min_s if min_s else SAFETY_CONFIG["ACTION_PAUSE_MIN"]
    high = max_s if max_s else SAFETY_CONFIG["ACTION_PAUSE_MAX"]
    time.sleep(random.uniform(low, high))

def human_move_to(target_x: int, target_y: int, steps: int = 12):
    """三阶平滑鼠标轨迹模拟"""
    try:
        curr_x, curr_y = win32api.GetCursorPos()
        for i in range(1, steps + 1):
            next_x = int(curr_x + (target_x - curr_x) * (i / steps))
            next_y = int(curr_y + (target_y - curr_y) * (i / steps))
            win32api.SetCursorPos((next_x, next_y))
            time.sleep(0.015)
        win32api.SetCursorPos((target_x, target_y))
        time.sleep(0.15)
    except Exception:
        pass

def human_click_at(target_x: int, target_y: int):
    """平滑移动并执行物理左键点击"""
    human_move_to(target_x, target_y)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(random.uniform(0.08, 0.12))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.2)

def set_clipboard_text(text: str):
    pyperclip.copy(text)
    time.sleep(0.1)

def paste_text():
    keyboard.send_keys('^v')
    time.sleep(0.1)

def force_foreground(hwnd: int):
    """跨线程强行置顶窗口并获取输入焦点"""
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    else:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

    curr_thread = win32api.GetCurrentThreadId()
    target_thread, _ = win32process.GetWindowThreadProcessId(hwnd)

    win32process.AttachThreadInput(curr_thread, target_thread, True)
    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # ALT按下
    win32gui.SetForegroundWindow(hwnd)
    ctypes.windll.user32.keybd_event(0x12, 0, 0x0002, 0)  # ALT释放
    win32gui.SetFocus(hwnd)
    win32process.AttachThreadInput(curr_thread, target_thread, False)
    time.sleep(0.3)
