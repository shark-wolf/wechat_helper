import time
import random
import win32gui
import win32con
import win32api
from pywinauto import Application
import pywinauto.keyboard as keyboard
from config import SAFETY_CONFIG, GREETING_POOL, load_coords, save_coord
from win_core import force_foreground, human_delay, set_clipboard_text, paste_text

def post_click(hwnd: int, rel_x: int, rel_y: int):
    """后台消息投递点击（不夺取物理鼠标光标）"""
    lparam = win32api.MAKELONG(rel_x, rel_y)
    win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
    time.sleep(0.08)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    time.sleep(0.12)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
    time.sleep(0.15)

def capture_click_relative(hwnd: int, timeout_sec: int = 20):
    """捕获物理鼠标点击并转为目标窗口相对坐标"""
    start_time = time.time()
    while win32api.GetAsyncKeyState(win32con.VK_LBUTTON) < 0:
        time.sleep(0.05)

    while time.time() - start_time < timeout_sec:
        if win32api.GetAsyncKeyState(win32con.VK_LBUTTON) < 0:
            abs_x, abs_y = win32api.GetCursorPos()
            rel_x, rel_y = win32gui.ScreenToClient(hwnd, (abs_x, abs_y))
            time.sleep(0.2)
            return rel_x, rel_y
        time.sleep(0.03)
    return None

def check_verify_dialog_exists() -> int:
    """检测右侧『申请添加朋友』弹窗是否已打开"""
    target_h = 0
    def enum_cb(h, _):
        nonlocal target_h
        if win32gui.IsWindowVisible(h):
            title = win32gui.GetWindowText(h)
            if "申请添加朋友" in title or "朋友验证" in title:
                target_h = h
                return False
        return True
    win32gui.EnumWindows(enum_cb, None)
    return target_h

class WeChatBot:
    def __init__(self, logger_callback=None, step_callback=None):
        self.log = logger_callback or (lambda msg: None)
        self.set_step = step_callback or (lambda step, status, color: None)
        self.target_calibration = None

    def find_wechat_hwnd(self) -> int:
        hwnd = win32gui.FindWindow("WeChatMainWndForPC", None)
        if hwnd and win32gui.IsWindow(hwnd):
            return hwnd

        target_hwnd = 0
        def enum_cb(h, _):
            nonlocal target_hwnd
            if win32gui.IsWindowVisible(h):
                title = win32gui.GetWindowText(h)
                cls_name = win32gui.GetClassName(h)
                if ("微信" in title or "WeChat" in title) and ("WeChat" in cls_name or "Qt" in cls_name):
                    target_hwnd = h
                    return False
            return True

        win32gui.EnumWindows(enum_cb, None)
        return target_hwnd

    def execute_add_pipeline(self, phone: str, remark_name: str = "", custom_greeting: str = "") -> str:
        coords = load_coords()
        try:
            # ----------------------------------------------------
            # 步骤 1: 唤醒置顶微信
            # ----------------------------------------------------
            self.set_step("CONNECT", "进行中...", "#D97706")
            hwnd = self.find_wechat_hwnd()
            if not hwnd:
                keyboard.send_keys('^%w')
                time.sleep(0.8)
                hwnd = self.find_wechat_hwnd()

            if not hwnd:
                self.set_step("CONNECT", "❌ 失败", "#DC2626")
                return "失败-未找到微信主窗口"

            force_foreground(hwnd)
            app = Application(backend="uia").connect(handle=hwnd)
            wechat_main = app.window(handle=hwnd)
            self.set_step("CONNECT", "✓ 完成", "#07C160")

            # ----------------------------------------------------
            # 步骤 2: 搜索框填入手机号
            # ----------------------------------------------------
            self.set_step("SEARCH", "静默搜号中...", "#D97706")
            self.log(f"激活搜索框并填入号码: {phone}")

            try:
                search_edit = wechat_main.child_window(title="搜索", control_type="Edit")
                if not search_edit.exists(timeout=0.3):
                    search_edit = wechat_main.child_window(control_type="Edit")
                if search_edit.exists(timeout=0.3):
                    search_edit.set_focus()
            except Exception:
                pass

            keyboard.send_keys('^f')
            time.sleep(0.25)
            keyboard.send_keys('^a{BACKSPACE}')
            time.sleep(0.2)

            set_clipboard_text(phone)
            paste_text()

            time.sleep(SAFETY_CONFIG["SEARCH_DEBOUNCE"])
            self.log("发送【向下键】选定网络查找项...")
            keyboard.send_keys('{DOWN}')
            time.sleep(0.25)

            self.log("发送【回车键】触发网络查找...")
            keyboard.send_keys('{ENTER}')
            self.set_step("SEARCH", "✓ 完成", "#07C160")

            # ----------------------------------------------------
            # 步骤 3: 状态闭环双探（有/无视频号自动适配）
            # ----------------------------------------------------
            self.set_step("CHECK_CARD", "检测卡片中...", "#D97706")
            self.log("等待『添加朋友』独立卡片弹窗...")
            human_delay(2.2, 3.0)

            add_friend_win = None
            for _ in range(6):
                for w in app.windows():
                    title = w.window_text().strip()
                    if "添加朋友" in title:
                        add_friend_win = w
                        break
                if add_friend_win:
                    break
                time.sleep(0.4)

            if not add_friend_win:
                for w in app.windows():
                    if w.handle != hwnd and w.rectangle().width() > 200:
                        add_friend_win = w
                        break

            if not add_friend_win:
                self.log("未检测到添加朋友窗体。")
                self.set_step("CHECK_CARD", "❌ 弹窗未出", "#DC2626")
                return "用户不存在/弹窗未出"

            force_foreground(add_friend_win.handle)
            time.sleep(0.4)

            # 好友查重
            already_friend = False
            for child in add_friend_win.children():
                if "发消息" in (child.window_text() or ""):
                    already_friend = True
                    break

            if already_friend:
                self.log("检测到『发消息』按钮：该用户已经是好友。")
                self.set_step("CHECK_CARD", "✓ 已是好友", "#2563EB")
                keyboard.send_keys('{ESC}')
                return "已是好友"

            if self.target_calibration in ["STEP3_NO_CHANNELS", "STEP3_HAS_CHANNELS"]:
                calib_name = "无视频号" if self.target_calibration == "STEP3_NO_CHANNELS" else "有视频号"
                self.log(f"🎯【定向标定】：请用鼠标在弹窗上点击【添加到通讯录】({calib_name})...")
                captured = capture_click_relative(add_friend_win.handle, timeout_sec=20)
                if captured:
                    save_coord(self.target_calibration, captured[0], captured[1])
                    coords[self.target_calibration] = list(captured)
                    self.log(f"✅ 已记录【{calib_name}】相对坐标: {captured} 并持久化！")
                else:
                    self.log(f"⚠️ 标定超时，使用默认坐标: {coords[self.target_calibration]}")
                    post_click(add_friend_win.handle, coords[self.target_calibration][0], coords[self.target_calibration][1])
            else:
                no_x, no_y = coords["STEP3_NO_CHANNELS"]
                has_x, has_y = coords["STEP3_HAS_CHANNELS"]

                self.log(f"👉 优先尝试【无视频号】基准坐标 ({no_x}, {no_y})...")
                post_click(add_friend_win.handle, no_x, no_y)
                time.sleep(0.8)

                if check_verify_dialog_exists():
                    self.log("✅ 确认弹窗已出现 -> 确定为【无视频号】名片！")
                else:
                    self.log(f"🔄 无响应，自动切换尝试【有视频号】推移坐标 ({has_x}, {has_y})...")
                    post_click(add_friend_win.handle, has_x, has_y)
                    time.sleep(0.8)
                    if check_verify_dialog_exists():
                        self.log("✅ 确认弹窗已出现 -> 确定为【有视频号】名片！")

            human_delay(1.0, 1.5)
            self.set_step("CHECK_CARD", "✓ 已点击添加", "#07C160")

            # ----------------------------------------------------
            # 步骤 4: 右侧『申请添加朋友』弹窗
            # ----------------------------------------------------
            self.set_step("SEND_VERIFY", "填写验证中...", "#D97706")
            self.log("等待右侧『申请添加朋友』弹窗...")

            verify_win = None
            for _ in range(8):
                v_h = check_verify_dialog_exists()
                if v_h:
                    for w in app.windows():
                        if w.handle == v_h:
                            verify_win = w
                            break
                    if verify_win:
                        break
                time.sleep(0.3)

            if not verify_win:
                self.log("未检测到申请添加朋友确认框。")
                self.set_step("SEND_VERIFY", "❌ 确认框未出", "#DC2626")
                return "申请弹窗未弹出"

            force_foreground(verify_win.handle)
            time.sleep(0.3)

            if self.target_calibration == "STEP4_CONFIRM_BTN":
                self.log("🎯【定向标定】：请用鼠标在右侧弹窗上点击【确定】按钮...")
                captured_btn = capture_click_relative(verify_win.handle, timeout_sec=20)
                if captured_btn:
                    save_coord("STEP4_CONFIRM_BTN", captured_btn[0], captured_btn[1])
                    coords["STEP4_CONFIRM_BTN"] = list(captured_btn)
                    self.log(f"✅ 已更新步骤4【确定按钮】相对坐标为: {captured_btn}！")
            else:
                all_edits = []
                try:
                    all_edits = verify_win.children(control_type="Edit")
                except Exception:
                    pass

                # 动态填充招呼语
                greeting = custom_greeting.strip() if custom_greeting and custom_greeting != "-" else random.choice(GREETING_POOL)
                self.log(f"填写验证招呼语: {greeting}")
                if all_edits:
                    try:
                        all_edits[0].click_input()
                    except Exception:
                        pass
                else:
                    post_click(verify_win.handle, coords["STEP4_GREETING_INPUT"][0], coords["STEP4_GREETING_INPUT"][1])

                time.sleep(0.2)
                set_clipboard_text(greeting)
                keyboard.send_keys('^a{BACKSPACE}')
                paste_text()
                human_delay(0.5, 0.8)

                # 动态填充备注名
                final_remark = remark_name.strip() if remark_name and remark_name != "-" else ""
                if final_remark:
                    self.log(f"设置备注名称: {final_remark}")
                    if len(all_edits) >= 2:
                        try:
                            all_edits[1].click_input()
                        except Exception:
                            pass
                    else:
                        post_click(verify_win.handle, coords["STEP4_REMARK_INPUT"][0], coords["STEP4_REMARK_INPUT"][1])

                    time.sleep(0.2)
                    set_clipboard_text(final_remark)
                    keyboard.send_keys('^a{BACKSPACE}')
                    paste_text()
                    human_delay(0.5, 0.8)

                # 点击确定
                btn_x, btn_y = coords["STEP4_CONFIRM_BTN"]
                self.log(f"后台点击确定按钮 -> 相对坐标 ({btn_x}, {btn_y})")
                post_click(verify_win.handle, btn_x, btn_y)

            time.sleep(0.3)
            keyboard.send_keys('{ENTER}')

            # 关闭残留
            time.sleep(0.8)
            keyboard.send_keys('{ESC}')

            human_delay(1.2, 1.8)
            self.set_step("SEND_VERIFY", "✓ 完成", "#07C160")
            return "成功-已发申请"

        except Exception as e:
            return f"异常: {e}"
