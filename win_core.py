import time
import random
import ctypes
import win32gui
import win32con
import win32process
import win32api
import pyperclip
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

def set_clipboard_text(text: str):
    pyperclip.copy(text)
    time.sleep(0.1)

def paste_text():
    import pywinauto.keyboard as keyboard
    keyboard.send_keys('^v')
    time.sleep(0.1)

def force_foreground(hwnd: int):
    """跨线程激活并置顶窗口"""
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    else:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

    curr_thread = win32api.GetCurrentThreadId()
    target_thread, _ = win32process.GetWindowThreadProcessId(hwnd)

    win32process.AttachThreadInput(curr_thread, target_thread, True)
    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
    win32gui.SetForegroundWindow(hwnd)
    ctypes.windll.user32.keybd_event(0x12, 0, 0x0002, 0)
    win32gui.SetFocus(hwnd)
    win32process.AttachThreadInput(curr_thread, target_thread, False)
    time.sleep(0.3)
