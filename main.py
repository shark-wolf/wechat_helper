import ctypes
import tkinter as tk
from config import APP_USER_MODEL_ID, SAFETY_CONFIG
from win_core import is_admin
from ui import WeChatAddApp

def set_app_user_model_id():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass

def bootstrap():
    set_app_user_model_id()
    root = tk.Tk()
    app = WeChatAddApp(root)

    if not is_admin():
        app.log("⚠️ 提示：未检测到管理员权限，若微信以管理员启动可能无法操控。")
    else:
        app.log("✅ 管理员权限确认就绪。")

    app.log(f"🛡️ 安全模式运行中：单日上限 {SAFETY_CONFIG['DAILY_MAX_LIMIT']} 个。")
    root.mainloop()

if __name__ == "__main__":
    bootstrap()
