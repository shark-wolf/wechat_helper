import os
import time
import random
import threading
import win32gui
import win32con
import win32api
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import pyperclip
from config import (
    THEME, STEPS, PAGE_SIZE, SAFETY_CONFIG, ICON_PATH,
    load_coords, save_coord, load_template_config, save_template_config
)
from wechat_bot import WeChatBot

class ModernButton(tk.Label):
    def __init__(self, parent, text, command=None, bg=THEME["primary"], hover_bg=THEME["primary_hover"], fg="white", font=("Microsoft YaHei UI", 9, "bold"), padx=12, pady=6, **kwargs):
        self.normal_bg = bg
        self.hover_bg = hover_bg
        self.command = command
        self.is_enabled = True
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady, cursor="hand2", relief=tk.FLAT, **kwargs)
        self.bind("<Enter>", lambda e: self.config(bg=self.hover_bg) if self.is_enabled else None)
        self.bind("<Leave>", lambda e: self.config(bg=self.normal_bg) if self.is_enabled else None)
        self.bind("<Button-1>", lambda e: self.command() if self.is_enabled and self.command else None)

    def set_state(self, state="normal", text=None, bg=None):
        if text:
            self.config(text=text)
        if state == "disabled":
            self.is_enabled = False
            self.config(bg=THEME["disabled_bg"], fg=THEME["disabled_fg"], cursor="arrow")
        else:
            self.is_enabled = True
            self.normal_bg = bg if bg else self.normal_bg
            self.config(bg=self.normal_bg, fg="white", cursor="hand2")

class WeChatAddApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PC微信半自动辅助添加工具 (Win7通用与动态模板版)")
        self.root.geometry("1180x920")
        self.root.configure(bg=THEME["bg"])

        if os.path.exists(ICON_PATH):
            try:
                self.root.iconbitmap(ICON_PATH)
            except Exception:
                pass

        self.df = None
        self.current_excel_path = None
        self.row_buttons = {}
        self.step_labels = {}
        self.current_page = 1
        self.total_pages = 1
        self.daily_added_count = 0
        self.is_batch_running = False
        self.cancel_requested = False

        self.selected_indices = set()
        self.all_selected = False

        self.template_cfg = load_template_config()

        self.bot = WeChatBot(logger_callback=self.log, step_callback=self.set_step_status)
        self.setup_styles()
        self.create_widgets()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"), background="#F3F4F6", foreground=THEME["text_main"], relief="flat", padding=6)
        style.configure("Treeview", font=("Microsoft YaHei UI", 9), background="white", fieldbackground="white", foreground=THEME["text_main"], rowheight=34, bordercolor=THEME["border"], borderwidth=1)
        style.map("Treeview", background=[("selected", "#E0F2FE")], foreground=[("selected", "#0369A1")])
        style.configure("Vertical.TScrollbar", gripcount=0, background="#D1D5DB", troughcolor="#F3F4F6", borderwidth=0, arrowsize=12)

    def create_widgets(self):
        # 顶部操作卡片
        top_card = tk.Frame(self.root, bg=THEME["card_bg"], highlightbackground=THEME["border"], highlightthickness=1)
        top_card.pack(fill=tk.X, padx=15, pady=(15, 8))
        top_inner = tk.Frame(top_card, bg=THEME["card_bg"], padx=15, pady=12)
        top_inner.pack(fill=tk.X)

        self.btn_import = ModernButton(top_inner, text="📁 导入 Excel", command=self.import_excel_file, bg=THEME["accent"], hover_bg=THEME["accent_hover"])
        self.btn_import.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_export_template = ModernButton(top_inner, text="📄 下载模板", command=self.export_excel_template, bg="#0284C7", hover_bg="#0369A1")
        self.btn_export_template.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_cfg_template = ModernButton(top_inner, text="⚙ 模板映射配置", command=self.open_template_config_dialog, bg="#6366F1", hover_bg="#4F46E5")
        self.btn_cfg_template.pack(side=tk.LEFT, padx=(0, 15))

        self.btn_export = ModernButton(top_inner, text="💾 导出结果", command=self.export_excel_file, bg="#4B5563", hover_bg="#374151")
        self.btn_export.pack(side=tk.LEFT, padx=(0, 15))

        self.btn_batch_start = ModernButton(top_inner, text="▶ 批量安全执行", command=self.toggle_batch_execution, bg=THEME["primary"], hover_bg=THEME["primary_hover"])
        self.btn_batch_start.pack(side=tk.LEFT, padx=(0, 15))

        self.btn_calib = ModernButton(top_inner, text="🎯 坐标标定模式", command=self.open_calibration_dialog, bg="#6B7280", hover_bg="#4B5563")
        self.btn_calib.pack(side=tk.LEFT, padx=(0, 15))

        self.lbl_selected_summary = tk.Label(top_inner, text="已勾选: 0 项", fg="#2563EB", bg=THEME["card_bg"], font=("Microsoft YaHei UI", 9, "bold"))
        self.lbl_selected_summary.pack(side=tk.LEFT, padx=10)

        self.lbl_daily_counter = tk.Label(top_inner, text=f"本日已发: {self.daily_added_count}/{SAFETY_CONFIG['DAILY_MAX_LIMIT']}", fg=THEME["text_main"], bg=THEME["card_bg"], font=("Microsoft YaHei UI", 9, "bold"))
        self.lbl_daily_counter.pack(side=tk.RIGHT, padx=5)

        # 表格卡片
        self.table_card = tk.Frame(self.root, bg=THEME["card_bg"], highlightbackground=THEME["border"], highlightthickness=1)
        self.table_card.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        self.table_inner = tk.Frame(self.table_card, bg=THEME["card_bg"], padx=10, pady=10)
        self.table_inner.pack(fill=tk.BOTH, expand=True)

        self.build_treeview_structure()

        page_card = tk.Frame(self.table_card, bg="#FAFAFA", highlightbackground=THEME["border"], highlightthickness=1)
        page_card.pack(fill=tk.X, padx=10, pady=(0, 10))
        page_inner = tk.Frame(page_card, bg="#FAFAFA", padx=10, pady=6)
        page_inner.pack(fill=tk.X)

        self.btn_prev = ModernButton(page_inner, text="◀ 上一页", command=self.prev_page, bg=THEME["accent"], hover_bg=THEME["accent_hover"], padx=8, pady=3, font=("Microsoft YaHei UI", 8, "bold"))
        self.btn_prev.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_page_info = tk.Label(page_inner, text="第 1 / 1 页 (共 0 条)", fg=THEME["text_main"], bg="#FAFAFA", font=("Microsoft YaHei UI", 9))
        self.lbl_page_info.pack(side=tk.LEFT, padx=10)

        self.btn_next = ModernButton(page_inner, text="下一页 ▶", command=self.next_page, bg=THEME["accent"], hover_bg=THEME["accent_hover"], padx=8, pady=3, font=("Microsoft YaHei UI", 8, "bold"))
        self.btn_next.pack(side=tk.LEFT, padx=(10, 20))

        # 执行状态卡片
        flow_card = tk.LabelFrame(self.root, text="  操作执行实时状态  ", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"], highlightbackground=THEME["border"], highlightthickness=1, padx=15, pady=6)
        flow_card.pack(fill=tk.X, padx=15, pady=6)

        for key, desc in STEPS:
            item_frame = tk.Frame(flow_card, bg=THEME["card_bg"])
            item_frame.pack(fill=tk.X, pady=1)
            tk.Label(item_frame, text=desc, font=("Microsoft YaHei UI", 9), fg=THEME["text_main"], bg=THEME["card_bg"], anchor="w").pack(side=tk.LEFT)
            status_lbl = tk.Label(item_frame, text="等待中", font=("Microsoft YaHei UI", 9, "bold"), fg="#9CA3AF", bg=THEME["card_bg"], width=14, anchor="e")
            status_lbl.pack(side=tk.RIGHT)
            self.step_labels[key] = status_lbl

        # 控制台卡片
        log_card = tk.LabelFrame(self.root, text="  安全运行控制台日志 (双击行复制 / 右键菜单)  ", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"], highlightbackground=THEME["border"], highlightthickness=1, padx=10, pady=6, height=130)
        log_card.pack_propagate(False)
        log_card.pack(fill=tk.X, padx=15, pady=(6, 15))

        self.log_text = tk.Text(log_card, height=5, wrap=tk.WORD, state=tk.DISABLED, bg="#111827", fg="#F3F4F6", font=("Consolas", 9), relief=tk.FLAT, padx=8, pady=6)
        log_scroll = ttk.Scrollbar(log_card, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text.bind("<Double-1>", self._on_log_double_click)
        self.log_text.bind("<Button-3>", self._show_log_context_menu)

    def build_treeview_structure(self):
        """动态生成 Treeview 表头列结构"""
        for child in self.table_inner.winfo_children():
            child.destroy()

        headers = self.template_cfg.get("headers", ["手机号", "客户姓名"])
        self.tree_columns = ["勾选", "序号"] + headers + ["状态", "操作"]

        self.tree = ttk.Treeview(self.table_inner, columns=self.tree_columns, show="headings", height=14)
        self.tree.heading("勾选", text="[  ] 全选", command=self.toggle_select_all)
        self.tree.column("勾选", width=65, anchor="center")

        self.tree.heading("序号", text="序号")
        self.tree.column("序号", width=60, anchor="center")

        for h in headers:
            self.tree.heading(h, text=h)
            self.tree.column(h, width=140, anchor="center")

        self.tree.heading("状态", text="状态")
        self.tree.column("状态", width=220, anchor="center")

        self.tree.heading("操作", text="操作")
        self.tree.column("操作", width=110, anchor="center")

        self.tree.bind("<ButtonRelease-1>", self.on_tree_cell_click)
        scrollbar = ttk.Scrollbar(self.table_inner, orient=tk.VERTICAL, command=self.on_scrollbar_scroll)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Configure>", lambda e: self.update_button_positions())
        self.tree.bind("<MouseWheel>", lambda e: self.root.after(50, self.update_button_positions))

    def open_template_config_dialog(self):
        """打开自定义 Excel 表头及列映射弹窗"""
        dialog = tk.Toplevel(self.root)
        dialog.title("自定义 Excel 模板与字段映射")
        dlg_w, dlg_h = 560, 480
        dialog.resizable(False, False)
        dialog.configure(bg=THEME["card_bg"])
        dialog.transient(self.root)

        root_x, root_y = self.root.winfo_x(), self.root.winfo_y()
        root_w, root_h = self.root.winfo_width(), self.root.winfo_height()
        pos_x = root_x + max(0, (root_w - dlg_w) // 2)
        pos_y = root_y + max(0, (root_h - dlg_h) // 2)
        dialog.geometry(f"{dlg_w}x{dlg_h}+{pos_x}+{pos_y}")

        cfg = load_template_config()

        tk.Label(dialog, text="定义 Excel 表头列名（用英文逗号分隔）：", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"]).pack(anchor="w", padx=25, pady=(15, 5))

        ent_headers = tk.Entry(dialog, font=("Consolas", 10), relief=tk.SOLID, bd=1)
        ent_headers.pack(fill=tk.X, padx=25, pady=(0, 15), ipady=4)
        ent_headers.insert(0, ", ".join(cfg.get("headers", [])))

        tk.Label(dialog, text="指定功能列映射（从上方表头中对应选择）：", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"]).pack(anchor="w", padx=25, pady=(0, 10))

        grid_frame = tk.Frame(dialog, bg=THEME["card_bg"])
        grid_frame.pack(fill=tk.X, padx=25)

        tk.Label(grid_frame, text="① 目标手机号列 (必选):", bg=THEME["card_bg"], font=("Microsoft YaHei UI", 9)).grid(row=0, column=0, sticky="w", pady=8)
        cbo_phone = ttk.Combobox(grid_frame, state="readonly", width=25)
        cbo_phone.grid(row=0, column=1, sticky="w", padx=10, pady=8)

        tk.Label(grid_frame, text="② 申请验证语列 (选填):", bg=THEME["card_bg"], font=("Microsoft YaHei UI", 9)).grid(row=1, column=0, sticky="w", pady=8)
        cbo_greeting = ttk.Combobox(grid_frame, state="readonly", width=25)
        cbo_greeting.grid(row=1, column=1, sticky="w", padx=10, pady=8)

        tk.Label(grid_frame, text="③ 微信备注名称列 (选填):", bg=THEME["card_bg"], font=("Microsoft YaHei UI", 9)).grid(row=2, column=0, sticky="w", pady=8)
        cbo_remark = ttk.Combobox(grid_frame, state="readonly", width=25)
        cbo_remark.grid(row=2, column=1, sticky="w", padx=10, pady=8)

        def sync_comboboxes(*args):
            raw = ent_headers.get().strip()
            cols = [c.strip() for c in raw.split(",") if c.strip()]
            for cbo in [cbo_phone, cbo_greeting, cbo_remark]:
                vals = ["(不指定/空)"] + cols if cbo != cbo_phone else cols
                cbo["values"] = vals
            if cbo_phone.get() not in cols and cols:
                cbo_phone.set(cols[0])

        ent_headers.bind("<KeyRelease>", sync_comboboxes)
        sync_comboboxes()

        if cfg.get("phone_col") in cbo_phone["values"]:
            cbo_phone.set(cfg["phone_col"])
        if cfg.get("greeting_col") in cbo_greeting["values"]:
            cbo_greeting.set(cfg["greeting_col"])
        else:
            cbo_greeting.set("(不指定/空)")
        if cfg.get("remark_col") in cbo_remark["values"]:
            cbo_remark.set(cfg["remark_col"])
        else:
            cbo_remark.set("(不指定/空)")

        def on_save_config():
            raw = ent_headers.get().strip()
            cols = [c.strip() for c in raw.split(",") if c.strip()]
            if not cols:
                messagebox.showerror("错误", "表头列表不能为空！")
                return
            p_col = cbo_phone.get().strip()
            if not p_col or p_col not in cols:
                messagebox.showerror("错误", "必须在表头中指定有效的【目标手机号列】！")
                return

            g_col = cbo_greeting.get().strip()
            if g_col == "(不指定/空)":
                g_col = ""
            r_col = cbo_remark.get().strip()
            if r_col == "(不指定/空)":
                r_col = ""

            new_cfg = {
                "headers": cols,
                "phone_col": p_col,
                "greeting_col": g_col,
                "remark_col": r_col
            }
            save_template_config(new_cfg)
            self.template_cfg = new_cfg

            self.build_treeview_structure()
            if self.df is not None:
                self.refresh_treeview()
            dialog.destroy()
            self.log(f"⚙️ 模板配置更新: 手机号列=[{p_col}], 招呼语列=[{g_col}], 备注列=[{r_col}]")
            messagebox.showinfo("成功", "模板配置及映射已生效！")

        btn_row = tk.Frame(dialog, bg=THEME["card_bg"])
        btn_row.pack(fill=tk.X, padx=25, pady=(25, 10))
        ModernButton(btn_row, text="保存配置", command=on_save_config, bg=THEME["primary"], hover_bg=THEME["primary_hover"]).pack(side=tk.RIGHT, padx=5)
        ModernButton(btn_row, text="取消", command=dialog.destroy, bg="#E5E7EB", hover_bg="#D1D5DB", fg="#374151").pack(side=tk.RIGHT, padx=5)

    def export_excel_template(self):
        """根据当前配置表头生成 Excel 模板"""
        headers = self.template_cfg.get("headers", ["手机号", "客户姓名", "申请打招呼语", "微信备注"])
        path = filedialog.asksaveasfilename(title="保存自定义模板文件", defaultextension=".xlsx", initialfile="微信添加好友导入模板.xlsx", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return

        demo_row = {}
        for h in headers:
            if h == self.template_cfg.get("phone_col"):
                demo_row[h] = "13800000000"
            elif h == self.template_cfg.get("greeting_col"):
                demo_row[h] = "你好，沟通业务，麻烦通过下"
            elif h == self.template_cfg.get("remark_col"):
                demo_row[h] = "张总-科技业务"
            else:
                demo_row[h] = "示例数据"

        tpl_df = pd.DataFrame([demo_row])
        try:
            tpl_df.to_excel(path, index=False)
            self.log(f"📄 模板文件已生成导出: {path}")
            messagebox.showinfo("成功", f"模板文件已成功导出至:\n{path}\n\n请按模板列名填入数据后点击【导入 Excel】。")
        except Exception as e:
            messagebox.showerror("导出失败", f"无法保存模板文件: {e}")

    def toggle_select_all(self):
        if self.df is None or self.df.empty:
            return
        if not self.all_selected:
            self.selected_indices = set(self.df.index.tolist())
            self.all_selected = True
            self.tree.heading("勾选", text="[√] 全选")
        else:
            self.selected_indices.clear()
            self.all_selected = False
            self.tree.heading("勾选", text="[  ] 全选")

        self.lbl_selected_summary.config(text=f"已勾选: {len(self.selected_indices)} 项")
        self.refresh_treeview(keep_page=True)

    def on_tree_cell_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        if col != "#1":
            return

        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        idx = int(row_id)
        if idx in self.selected_indices:
            self.selected_indices.remove(idx)
        else:
            self.selected_indices.add(idx)

        chk_char = "[√]" if idx in self.selected_indices else "[  ]"
        vals = list(self.tree.item(row_id, "values"))
        vals[0] = chk_char
        self.tree.item(row_id, values=vals)
        self.lbl_selected_summary.config(text=f"已勾选: {len(self.selected_indices)} 项")

    def open_calibration_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("选择坐标标定目标 (实时捕获)")
        dlg_w, dlg_h = 600, 420
        dialog.resizable(False, False)
        dialog.configure(bg=THEME["card_bg"])
        dialog.transient(self.root)

        root_x, root_y = self.root.winfo_x(), self.root.winfo_y()
        root_w, root_h = self.root.winfo_width(), self.root.winfo_height()
        pos_x = root_x + max(0, (root_w - dlg_w) // 2)
        pos_y = root_y + max(0, (root_h - dlg_h) // 2)
        dialog.geometry(f"{dlg_w}x{dlg_h}+{pos_x}+{pos_y}")

        coords = load_coords()
        staged_coords = coords.copy()

        calib_var = tk.StringVar(value="NONE")
        listen_active = [False]

        tk.Label(dialog, text="选择标定项后，鼠标直接在微信对应窗口上点击目标按钮进行采集：", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"]).pack(anchor="w", padx=25, pady=(15, 6))

        lbl_hint = tk.Label(dialog, text="💡 当前状态: 未开启采集，请单选具体目标项", font=("Microsoft YaHei UI", 9), bg="#EFF6FF", fg="#1D4ED8", padx=10, pady=4, relief=tk.SOLID, bd=1)
        lbl_hint.pack(fill=tk.X, padx=25, pady=(0, 10))

        opts = [
            ("NONE", "全自动正常模式 (不标定)", "沿用历史配置"),
            ("STEP3_NO_CHANNELS", "步骤 3:【无视频号】添加到通讯录", "STEP3_NO_CHANNELS"),
            ("STEP3_HAS_CHANNELS", "步骤 3:【有视频号】添加到通讯录", "STEP3_HAS_CHANNELS"),
            ("STEP4_CONFIRM_BTN", "步骤 4: 申请弹窗【确定】按钮", "STEP4_CONFIRM_BTN")
        ]

        card_group = tk.Frame(dialog, bg=THEME["card_bg"])
        card_group.pack(fill=tk.BOTH, expand=True, padx=25)
        val_labels = {}

        for val, label, key_name in opts:
            row_frame = tk.Frame(card_group, bg="#F9FAFB", highlightbackground=THEME["border"], highlightthickness=1)
            row_frame.pack(fill=tk.X, pady=3, ipady=3)

            rb = tk.Radiobutton(row_frame, text=label, variable=calib_var, value=val, font=("Microsoft YaHei UI", 9, "bold"), bg="#F9FAFB", activebackground="#F9FAFB", fg=THEME["text_main"], command=lambda: on_radio_select())
            rb.pack(side=tk.LEFT, padx=10)

            if val == "NONE":
                lbl_val = tk.Label(row_frame, text="(不执行点击捕获)", font=("Consolas", 8), fg="#6B7280", bg="#F9FAFB")
            else:
                lbl_val = tk.Label(row_frame, text=f"当前坐标: {coords.get(key_name)}", font=("Consolas", 9, "bold"), fg="#2563EB", bg="#F9FAFB")
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

            while listen_active[0] and calib_var.get() == chosen_key:
                if win32api.GetAsyncKeyState(win32con.VK_LBUTTON) < 0:
                    abs_x, abs_y = win32api.GetCursorPos()
                    hwnd = find_target_panel_hwnd(chosen_key)
                    if hwnd:
                        w_left, w_top, w_right, w_bottom = win32gui.GetWindowRect(hwnd)
                        if w_left <= abs_x <= w_right and w_top <= abs_y <= w_bottom:
                            rel_x, rel_y = win32gui.ScreenToClient(hwnd, (abs_x, abs_y))
                            staged_coords[chosen_key] = [rel_x, rel_y]
                            dialog.after(0, lambda k=chosen_key, c=(rel_x, rel_y): on_captured_success(k, c))
                    time.sleep(0.25)
                time.sleep(0.03)

        def on_captured_success(chosen_key, coord):
            if chosen_key in val_labels:
                val_labels[chosen_key].config(text=f"已捕获最新: {list(coord)}", fg="#059669")
                lbl_hint.config(text=f"🎯 成功捕获到相对坐标 {coord}！点击【确认设置并保存】写入配置。", bg="#ECFDF5", fg="#047857")

        def on_radio_select():
            chosen = calib_var.get()
            if chosen == "NONE":
                listen_active[0] = False
                lbl_hint.config(text="💡 当前状态: 未开启采集，请单选具体目标项", bg="#EFF6FF", fg="#1D4ED8")
            else:
                listen_active[0] = False
                time.sleep(0.08)
                listen_active[0] = True
                lbl_hint.config(text=f"🎯 正在监听鼠标点击！请在屏幕上直接点击微信面板对应的目标按钮...", bg="#FEF3C7", fg="#B45309")
                threading.Thread(target=listen_worker, args=(chosen,), daemon=True).start()

        def on_confirm():
            listen_active[0] = False
            for k in ["STEP3_NO_CHANNELS", "STEP3_HAS_CHANNELS", "STEP4_CONFIRM_BTN"]:
                if staged_coords[k] != coords.get(k):
                    save_coord(k, staged_coords[k][0], staged_coords[k][1])
                    self.log(f"💾【配置已更新】{k} -> 相对坐标已更新保存为: {staged_coords[k]}")

            self.bot.target_calibration = None
            self.btn_calib.config(text="🎯 坐标标定模式", bg="#6B7280")
            dialog.destroy()
            messagebox.showinfo("成功", "标定坐标已确认并成功更新保存！")

        btn_row = tk.Frame(dialog, bg=THEME["card_bg"])
        btn_row.pack(fill=tk.X, padx=25, pady=(15, 18))
        ModernButton(btn_row, text="确认设置并保存", command=on_confirm, bg=THEME["primary"], hover_bg=THEME["primary_hover"]).pack(side=tk.RIGHT, padx=5)
        ModernButton(btn_row, text="取消", command=lambda: (listen_active.clear(), dialog.destroy()), bg="#E5E7EB", hover_bg="#D1D5DB", fg="#374151").pack(side=tk.RIGHT, padx=5)

    def _on_log_double_click(self, event):
        try:
            line_idx = self.log_text.index(f"@{event.x},{event.y} linestart")
            line_end = self.log_text.index(f"@{event.x},{event.y} lineend")
            line_content = self.log_text.get(line_idx, line_end).strip()
            if line_content:
                pyperclip.copy(line_content)
                self._show_copy_toast(event.x_root, event.y_root, "已复制单行日志")
        except Exception:
            pass

    def _show_log_context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        has_sel = False
        try:
            sel_text = self.log_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if sel_text:
                has_sel = True
                menu.add_command(label="复制选中内容", command=lambda: pyperclip.copy(sel_text))
        except Exception:
            pass

        if not has_sel:
            try:
                line_idx = self.log_text.index(f"@{event.x},{event.y} linestart")
                line_end = self.log_text.index(f"@{event.x},{event.y} lineend")
                line_content = self.log_text.get(line_idx, line_end).strip()
                if line_content:
                    menu.add_command(label="复制当前行", command=lambda: pyperclip.copy(line_content))
            except Exception:
                pass

        menu.add_command(label="复制全部日志", command=self._copy_all_logs)
        menu.add_command(label="查看当前有效坐标配置", command=self._show_current_coords)
        menu.add_separator()
        menu.add_command(label="清空日志控制台", command=self._clear_logs)
        menu.post(event.x_root, event.y_root)

    def _show_current_coords(self):
        c = load_coords()
        msg = f"当前已保存的相对坐标：\n• 步骤3(无视频号): {c.get('STEP3_NO_CHANNELS')}\n• 步骤3(有视频号): {c.get('STEP3_HAS_CHANNELS')}\n• 步骤4(确定按钮): {c.get('STEP4_CONFIRM_BTN')}"
        messagebox.showinfo("当前坐标配置", msg)

    def _copy_all_logs(self):
        full_text = self.log_text.get("1.0", tk.END).strip()
        if full_text:
            pyperclip.copy(full_text)
            self.log("📋 全量控制台日志已复制到剪贴板。")

    def _clear_logs(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _show_copy_toast(self, x, y, msg="已复制"):
        toast = tk.Toplevel(self.root)
        toast.wm_overrideredirect(True)
        toast.geometry(f"+{x+10}+{y-20}")
        toast.attributes("-topmost", True)
        lbl = tk.Label(toast, text=f" ✓ {msg} ", bg="#1F2937", fg="#10B981", font=("Microsoft YaHei UI", 8, "bold"), padx=6, pady=2, relief=tk.SOLID, bd=1)
        lbl.pack()
        self.root.after(1000, toast.destroy)

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_treeview(keep_page=True)

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.refresh_treeview(keep_page=True)

    def update_page_info(self):
        total_records = len(self.df) if self.df is not None else 0
        self.total_pages = max(1, (total_records + PAGE_SIZE - 1) // PAGE_SIZE)
        self.current_page = min(self.current_page, self.total_pages)
        self.lbl_page_info.config(text=f"第 {self.current_page} / {self.total_pages} 页 (共 {total_records} 条记录)")
        self.btn_prev.set_state("disabled" if self.current_page <= 1 else "normal")
        self.btn_next.set_state("disabled" if self.current_page >= self.total_pages else "normal")

    def set_step_status(self, step_key: str, status: str, color: str = "#9CA3AF"):
        self.root.after(0, lambda: self.step_labels[step_key].config(text=status, fg=color) if step_key in self.step_labels else None)

    def reset_step_status(self):
        for key, _ in STEPS:
            self.set_step_status(key, "等待中", "#9CA3AF")

    def log(self, message: str):
        def append():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, time.strftime("[%H:%M:%S] ") + message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.root.after(0, append)

    def on_scrollbar_scroll(self, *args):
        self.tree.yview(*args)
        self.update_button_positions()

    def import_excel_file(self):
        path = filedialog.askopenfilename(title="选择 Excel 文件", filetypes=[("Excel", "*.xlsx *.xls"), ("All", "*.*")])
        if not path:
            return
        try:
            df = pd.read_excel(path)
            phone_col = self.template_cfg.get("phone_col", "手机号")
            if phone_col not in df.columns:
                messagebox.showerror("格式错误", f"当前映射的手机号列【{phone_col}】在导入的表格中不存在！\n请通过【⚙ 模板映射配置】重新指定。")
                return

            if "状态" not in df.columns:
                df["状态"] = "未添加"

            self.df = df
            self.current_excel_path = path
            self.current_page = 1
            self.selected_indices.clear()
            self.all_selected = False
            self.tree.heading("勾选", text="[  ] 全选")
            self.lbl_selected_summary.config(text="已勾选: 0 项")
            self.refresh_treeview()
            self.log(f"✅ 成功载入数据: {os.path.basename(path)}，共 {len(self.df)} 条 (手机号列: {phone_col})")
        except Exception as e:
            self.log(f"❌ 导入失败: {e}")

    def export_excel_file(self):
        if self.df is None or self.df.empty:
            messagebox.showinfo("提示", "当前无数据导出！")
            return
        path = filedialog.asksaveasfilename(title="导出结果", defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if path:
            self.df.to_excel(path, index=False)
            messagebox.showinfo("成功", f"结果已导出至:\n{path}")

    def refresh_treeview(self, keep_page=False):
        for btn in self.row_buttons.values():
            btn.destroy()
        self.row_buttons.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.update_page_info()
        if self.df is not None and not self.df.empty:
            start = (self.current_page - 1) * PAGE_SIZE
            end = min(start + PAGE_SIZE, len(self.df))
            headers = self.template_cfg.get("headers", ["手机号", "客户姓名"])

            for idx, row in self.df.iloc[start:end].iterrows():
                chk_char = "[√]" if idx in self.selected_indices else "[  ]"

                row_vals = [chk_char, idx + 1]
                for h in headers:
                    val = str(row[h]).strip() if h in row and pd.notna(row[h]) else "-"
                    row_vals.append(val)

                status_val = str(row["状态"]) if "状态" in row and pd.notna(row["状态"]) else "未添加"
                row_vals.append(status_val)
                row_vals.append("")

                self.tree.insert("", tk.END, iid=idx, values=row_vals)
                btn = ModernButton(self.tree, text="➕ 单个添加", command=lambda i=idx: self.start_single_task(i), padx=6, pady=2)
                self.row_buttons[idx] = btn
            self.root.after(150, self.update_button_positions)

    def update_button_positions(self):
        if self.df is None or self.df.empty:
            return
        for idx, btn in self.row_buttons.items():
            bbox = self.tree.bbox(idx, column="操作")
            if bbox and len(bbox) == 4:
                btn.place(x=bbox[0]+10, y=bbox[1]+3, width=bbox[2]-20, height=bbox[3]-6)
            else:
                btn.place_forget()

    def start_single_task(self, idx: int):
        if self.is_batch_running:
            messagebox.showwarning("冲突", "批量任务正在执行中！")
            return
        threading.Thread(target=self._run_task_pipeline, args=(idx,), daemon=True).start()

    def toggle_batch_execution(self):
        if self.is_batch_running:
            self.cancel_requested = True
            self.log("🛑 正在停止批量任务...")
            self.btn_batch_start.set_state("disabled", text="正在停止...")
            return

        if self.df is None or self.df.empty:
            messagebox.showwarning("提示", "请先导入数据！")
            return

        # 严格拦截：未勾选任何行时弹出提示
        if not self.selected_indices:
            messagebox.showwarning("提示", "请勾选需要执行的行！")
            return

        pending = [
            i for i in sorted(list(self.selected_indices))
            if not ("成功" in str(self.df.at[i, "状态"]) or "已是好友" in str(self.df.at[i, "状态"]))
        ]

        if not pending:
            messagebox.showinfo("提示", "勾选的所有条目均已添加成功或已是好友！")
            return

        self.log(f"📋 执行模式：执行【勾选指定项】，待处理: {len(pending)} 个")

        self.is_batch_running = True
        self.cancel_requested = False
        self.btn_batch_start.set_state("normal", text="⏹ 停止批量任务", bg=THEME["warning"])
        threading.Thread(target=self._run_batch_worker, args=(pending,), daemon=True).start()

    def _run_batch_worker(self, target_indices):
        phone_col = self.template_cfg.get("phone_col", "手机号")
        self.log(f"🛡️ 启动批量调度，总计: {len(target_indices)} 个任务")
        for i, idx in enumerate(target_indices):
            if self.cancel_requested or self.daily_added_count >= SAFETY_CONFIG["DAILY_MAX_LIMIT"]:
                break
            phone = str(self.df.at[idx, phone_col]).strip()
            self.log(f"👉 [{i+1}/{len(target_indices)}] 准备添加: {phone}")
            result = self._run_task_pipeline(idx)
            if any(k in result for k in ["频繁", "限制", "封禁"]):
                self.log("🚨 命中风控熔断，紧急挂起全部任务！")
                break
            if i < len(target_indices) - 1 and not self.cancel_requested:
                cooldown = random.randint(SAFETY_CONFIG["MIN_COOLDOWN_SEC"], SAFETY_CONFIG["MAX_COOLDOWN_SEC"])
                for s in range(cooldown, 0, -1):
                    if self.cancel_requested:
                        break
                    if s % 5 == 0 or s <= 3:
                        self.log(f"⏳ 拟人安全冷却剩余 {s} 秒...")
                    time.sleep(1)

        self.is_batch_running = False
        self.root.after(0, lambda: self.btn_batch_start.set_state("normal", text="▶ 批量安全执行", bg=THEME["primary"]))
        self.log("🏁 批量任务调度结束。")

    def _run_task_pipeline(self, idx: int) -> str:
        phone_col = self.template_cfg.get("phone_col", "手机号")
        greeting_col = self.template_cfg.get("greeting_col", "")
        remark_col = self.template_cfg.get("remark_col", "")

        phone = str(self.df.at[idx, phone_col]).strip()

        greeting = ""
        if greeting_col and greeting_col in self.df.columns and pd.notna(self.df.at[idx, greeting_col]):
            greeting = str(self.df.at[idx, greeting_col]).strip()

        remark = ""
        if remark_col and remark_col in self.df.columns and pd.notna(self.df.at[idx, remark_col]):
            remark = str(self.df.at[idx, remark_col]).strip()

        self.reset_step_status()

        btn = self.row_buttons.get(idx)
        if btn:
            self.root.after(0, lambda: btn.set_state("disabled", text="执行中..."))

        result = self.bot.execute_add_pipeline(phone, remark_name=remark, custom_greeting=greeting)
        self.df.at[idx, "状态"] = result
        if "成功" in result:
            self.daily_added_count += 1
            self.root.after(0, lambda: self.lbl_daily_counter.config(text=f"本日已发: {self.daily_added_count}/{SAFETY_CONFIG['DAILY_MAX_LIMIT']}"))

        self.root.after(0, lambda: self._update_row_view(idx, result))
        return result

    def _update_row_view(self, idx: int, result: str):
        if self.tree.exists(idx):
            vals = list(self.tree.item(idx, "values"))
            vals[-2] = result
            self.tree.item(idx, values=vals)
        btn = self.row_buttons.get(idx)
        if btn:
            is_done = "成功" in result or "已是好友" in result
            btn.set_state("normal", text="✓ 完成" if is_done else "➕ 重试")
        self.update_button_positions()
