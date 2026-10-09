import time
import threading
import win32gui
import win32api
import win32con
import tkinter as tk
from tkinter import messagebox
from config import THEME, load_coords, save_coord
from ui_components import ModernButton

class CalibrationDialog(tk.Toplevel):
    def __init__(self, parent, bot_instance, log_callback=None):
        super().__init__(parent)
        self.app = parent
        self.bot = bot_instance
        self.log = log_callback or (lambda msg: None)

        self.title("选择坐标标定目标 (实时捕获)")
        dlg_w, dlg_h = 600, 420
        self.resizable(False, False)
        self.configure(bg=THEME["card_bg"])
        self.transient(parent)

        root_x, root_y = parent.winfo_x(), parent.winfo_y()
        root_w, root_h = parent.winfo_width(), parent.winfo_height()
        pos_x = root_x + max(0, (root_w - dlg_w) // 2)
        pos_y = root_y + max(0, (root_h - dlg_h) // 2)
        self.geometry(f"{dlg_w}x{dlg_h}+{pos_x}+{pos_y}")

        self.coords = load_coords()
        self.staged_coords = self.coords.copy()
        self.calib_var = tk.StringVar(value="NONE")
        self.listen_active = [False]

        self._create_widgets()

    def _create_widgets(self):
        tk.Label(self, text="选择标定项后，鼠标直接在微信对应窗口上点击目标按钮进行采集：", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"]).pack(anchor="w", padx=25, pady=(15, 6))

        lbl_hint = tk.Label(self, text="💡 当前状态: 未开启采集，请单选具体目标项", font=("Microsoft YaHei UI", 9), bg="#EFF6FF", fg="#1D4ED8", padx=10, pady=4, relief=tk.SOLID, bd=1)
        lbl_hint.pack(fill=tk.X, padx=25, pady=(0, 10))

        opts = [
            ("NONE", "全自动正常模式 (不标定)", "沿用历史配置"),
            ("STEP3_NO_CHANNELS", "步骤 3:【无视频号】添加到通讯录", "STEP3_NO_CHANNELS"),
            ("STEP3_HAS_CHANNELS", "步骤 3:【有视频号】添加到通讯录", "STEP3_HAS_CHANNELS"),
            ("STEP4_CONFIRM_BTN", "步骤 4: 申请弹窗【确定】按钮", "STEP4_CONFIRM_BTN")
        ]

        card_group = tk.Frame(self, bg=THEME["card_bg"])
        card_group.pack(fill=tk.BOTH, expand=True, padx=25)
        val_labels = {}

        for val, label, key_name in opts:
            row_frame = tk.Frame(card_group, bg="#F9FAFB", highlightbackground=THEME["border"], highlightthickness=1)
            row_frame.pack(fill=tk.X, pady=3, ipady=3)

            rb = tk.Radiobutton(row_frame, text=label, variable=self.calib_var, value=val, font=("Microsoft YaHei UI", 9, "bold"), bg="#F9FAFB", activebackground="#F9FAFB", fg=THEME["text_main"], command=lambda: on_radio_select())
            rb.pack(side=tk.LEFT, padx=10)

            if val == "NONE":
                lbl_val = tk.Label(row_frame, text="(不执行点击捕获)", font=("Consolas", 8), fg="#6B7280", bg="#F9FAFB")
            else:
                lbl_val = tk.Label(row_frame, text=f"当前坐标: {self.coords.get(key_name)}", font=("Consolas", 9, "bold"), fg="#2563EB", bg="#F9FAFB")
                val_labels[key_name] = lbl_val
            lbl_val.pack(side=tk.RIGHT, padx=12)

        def find_target_panel_hwnd(chosen_key):
            target_title = "申请添加朋友" if chosen_key == "STEP4_CONFIRM_BTN" else "添加朋友"
            found_h = 0
            def enum_w(h, _):
                nonlocal found_h
                if win32gui.IsWindowVisible(h):
                    t = win32gui.GetWindowText(h)
                    if target_title in t:
                        found_h = h
                        return False
                return True
            win32gui.EnumWindows(enum_w, None)
            return found_h

        def listen_worker(chosen_key):
            time.sleep(0.3)
            while win32api.GetAsyncKeyState(win32con.VK_LBUTTON) < 0:
                time.sleep(0.05)

            while self.listen_active[0] and self.calib_var.get() == chosen_key:
                if win32api.GetAsyncKeyState(win32con.VK_LBUTTON) < 0:
                    abs_x, abs_y = win32api.GetCursorPos()
                    hwnd = find_target_panel_hwnd(chosen_key)
                    if hwnd:
                        w_left, w_top, w_right, w_bottom = win32gui.GetWindowRect(hwnd)
                        if w_left <= abs_x <= w_right and w_top <= abs_y <= w_bottom:
                            rel_x, rel_y = win32gui.ScreenToClient(hwnd, (abs_x, abs_y))
                            self.staged_coords[chosen_key] = [rel_x, rel_y]
                            self.after(0, lambda k=chosen_key, c=(rel_x, rel_y): on_captured_success(k, c))
                    time.sleep(0.25)
                time.sleep(0.03)

        def on_captured_success(chosen_key, coord):
            if chosen_key in val_labels:
                val_labels[chosen_key].config(text=f"已捕获最新: {list(coord)}", fg="#059669")
                lbl_hint.config(text=f"🎯 成功捕获到相对坐标 {coord}！点击【确认设置并保存】写入配置。", bg="#ECFDF5", fg="#047857")

        def on_radio_select():
            chosen = self.calib_var.get()
            if chosen == "NONE":
                self.listen_active[0] = False
                lbl_hint.config(text="💡 当前状态: 未开启采集，请单选具体目标项", bg="#EFF6FF", fg="#1D4ED8")
            else:
                self.listen_active[0] = False
                time.sleep(0.08)
                self.listen_active[0] = True
                lbl_hint.config(text=f"🎯 正在监听鼠标点击！请在屏幕上直接点击微信面板对应的目标按钮...", bg="#FEF3C7", fg="#B45309")
                threading.Thread(target=listen_worker, args=(chosen,), daemon=True).start()

        def on_confirm():
            self.listen_active[0] = False
            for k in ["STEP3_NO_CHANNELS", "STEP3_HAS_CHANNELS", "STEP4_CONFIRM_BTN"]:
                if self.staged_coords[k] != self.coords.get(k):
                    save_coord(k, self.staged_coords[k][0], self.staged_coords[k][1])
                    self.log(f"💾【配置已更新】{k} -> 相对坐标已更新保存为: {self.staged_coords[k]}")

            self.bot.target_calibration = None
            self.destroy()
            messagebox.showinfo("成功", "标定坐标已确认并成功更新保存！")

        btn_row = tk.Frame(self, bg=THEME["card_bg"])
        btn_row.pack(fill=tk.X, padx=25, pady=(15, 18))
        ModernButton(btn_row, text="确认设置并保存", command=on_confirm, bg=THEME["primary"], hover_bg=THEME["primary_hover"]).pack(side=tk.RIGHT, padx=5)
        ModernButton(btn_row, text="取消", command=lambda: (self.listen_active.clear(), self.destroy()), bg="#E5E7EB", hover_bg="#D1D5DB", fg="#374151").pack(side=tk.RIGHT, padx=5)
