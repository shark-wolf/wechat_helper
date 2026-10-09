import os
import time
import random
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import pyperclip

import config
from config import (
    THEME, STEPS, ICON_PATH,
    load_coords, load_template_config, load_success_phones, record_success_phone,
    load_safety_config, save_safety_config
)
from wechat_bot import WeChatBot
from ui_components import ModernButton, parse_placeholders
from ui_dialog_template import TemplateConfigDialog
from ui_dialog_calibration import CalibrationDialog
from ui_dialog_safety import SafetyConfigDialog

class WeChatAddApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PC微信半自动辅助添加工具")
        self.root.geometry("1900x1300")
        self.root.configure(bg=THEME["bg"])

        # 绑定窗口关闭事件 (WM_DELETE_WINDOW)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        if os.path.exists(ICON_PATH):
            try:
                self.root.iconbitmap(ICON_PATH)
            except Exception:
                pass

        self.df = None
        self.df_lock = threading.Lock()
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
        self.safety_cfg = load_safety_config()
        # 从配置动态初始化 page_size
        self.page_size = int(self.safety_cfg.get("PAGE_SIZE", 15))
        config.SAFETY_CONFIG.update(self.safety_cfg)

        self.bot = WeChatBot(logger_callback=self.log, step_callback=self.set_step_status)

        self.setup_styles()
        self.create_widgets()

    def on_closing(self):
        """点击右上角关闭按钮时的优雅退出机制"""
        if self.is_batch_running:
            if messagebox.askyesno("确认退出", "批量添加任务正在运行中，确定要中断任务并退出程序吗？"):
                self.cancel_requested = True
                self.log("🛑 正在中断后台任务并安全退出...")
                self.root.after(300, self._force_exit)
        else:
            self._force_exit()

    def _force_exit(self):
        """销毁窗口并彻底清除后台残留进程"""
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"), background="#F3F4F6", foreground=THEME["text_main"], relief="flat", padding=6)
        style.configure("Treeview", font=("Microsoft YaHei UI", 9), background="white", fieldbackground="white", foreground=THEME["text_main"], rowheight=34, bordercolor=THEME["border"], borderwidth=1)
        style.map("Treeview", background=[("selected", "#E0F2FE")], foreground=[("selected", "#0369A1")])
        style.configure("Vertical.TScrollbar", gripcount=0, background="#D1D5DB", troughcolor="#F3F4F6", borderwidth=0, arrowsize=12)

    def create_widgets(self):
        top_card = tk.Frame(self.root, bg=THEME["card_bg"], highlightbackground=THEME["border"], highlightthickness=1)
        top_card.pack(fill=tk.X, padx=15, pady=(15, 8))
        top_inner = tk.Frame(top_card, bg=THEME["card_bg"], padx=15, pady=12)
        top_inner.pack(fill=tk.X)

        self.btn_import = ModernButton(top_inner, text="📁 导入 Excel", command=self.import_excel_file, bg=THEME["accent"], hover_bg=THEME["accent_hover"])
        self.btn_import.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_export_template = ModernButton(top_inner, text="📄 下载模板", command=self.export_excel_template, bg="#0284C7", hover_bg="#0369A1")
        self.btn_export_template.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_cfg_template = ModernButton(top_inner, text="⚙ 模板映射配置", command=self.open_template_config_dialog, bg="#6366F1", hover_bg="#4F46E5")
        self.btn_cfg_template.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_cfg_safety = ModernButton(top_inner, text="🛡️ 安全参数设置", command=self.open_safety_config_dialog, bg="#059669", hover_bg="#047857")
        self.btn_cfg_safety.pack(side=tk.LEFT, padx=(0, 15))

        self.btn_export = ModernButton(top_inner, text="💾 导出结果", command=self.export_excel_file, bg="#4B5563", hover_bg="#374151")
        self.btn_export.pack(side=tk.LEFT, padx=(0, 15))

        self.btn_batch_start = ModernButton(top_inner, text="▶ 批量安全执行", command=self.toggle_batch_execution, bg=THEME["primary"], hover_bg=THEME["primary_hover"])
        self.btn_batch_start.pack(side=tk.LEFT, padx=(0, 15))

        self.btn_calib = ModernButton(top_inner, text="🎯 坐标标定模式", command=self.open_calibration_dialog, bg="#6B7280", hover_bg="#4B5563")
        self.btn_calib.pack(side=tk.LEFT, padx=(0, 15))

        self.lbl_selected_summary = tk.Label(top_inner, text="已勾选: 0 项", fg="#2563EB", bg=THEME["card_bg"], font=("Microsoft YaHei UI", 9, "bold"))
        self.lbl_selected_summary.pack(side=tk.LEFT, padx=10)

        self.lbl_daily_counter = tk.Label(top_inner, text=f"本日已发: {self.daily_added_count}/{self.safety_cfg['DAILY_MAX_LIMIT']}", fg=THEME["text_main"], bg=THEME["card_bg"], font=("Microsoft YaHei UI", 9, "bold"))
        self.lbl_daily_counter.pack(side=tk.RIGHT, padx=5)

        # 表格卡片
        self.table_card = tk.Frame(self.root, bg=THEME["card_bg"], highlightbackground=THEME["border"], highlightthickness=1)
        self.table_card.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        self.table_inner = tk.Frame(self.table_card, bg=THEME["card_bg"], padx=10, pady=10)
        self.table_inner.pack(fill=tk.BOTH, expand=True)

        self.build_treeview_structure()

        # 分页控制器卡片
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

        # UI 每页条数快捷选择器
        tk.Label(page_inner, text="每页显示:", fg=THEME["text_sub"], bg="#FAFAFA", font=("Microsoft YaHei UI", 8)).pack(side=tk.LEFT, padx=(10, 2))
        self.cbo_ui_page_size = ttk.Combobox(page_inner, values=["10", "15", "20", "30", "50", "100"], width=6, state="readonly")
        self.cbo_ui_page_size.set(str(self.page_size))
        self.cbo_ui_page_size.pack(side=tk.LEFT, padx=2)
        self.cbo_ui_page_size.bind("<<ComboboxSelected>>", self.on_page_size_changed)
        tk.Label(page_inner, text="条", fg=THEME["text_sub"], bg="#FAFAFA", font=("Microsoft YaHei UI", 8)).pack(side=tk.LEFT)

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

        # 控制台卡片：增加高度至 240，提升日志可视行数
        log_card = tk.LabelFrame(self.root, text="  安全运行控制台日志 (双击行复制 / 右键菜单)  ", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"], highlightbackground=THEME["border"], highlightthickness=1, padx=10, pady=6, height=240)
        log_card.pack_propagate(False)
        log_card.pack(fill=tk.X, padx=15, pady=(6, 15))

        self.log_text = tk.Text(log_card, wrap=tk.WORD, state=tk.DISABLED, bg="#111827", fg="#F3F4F6", font=("Consolas", 9), relief=tk.FLAT, padx=8, pady=6)
        log_scroll = ttk.Scrollbar(log_card, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text.bind("<Double-1>", self._on_log_double_click)
        self.log_text.bind("<Button-3>", self._show_log_context_menu)

    def on_page_size_changed(self, event=None):
        """当用户在 UI 下拉框切换每页显示条数时触发"""
        val = int(self.cbo_ui_page_size.get())
        if val != self.page_size:
            self.page_size = val
            self.safety_cfg["PAGE_SIZE"] = val
            save_safety_config(self.safety_cfg)
            self.current_page = 1
            self.refresh_treeview()
            self.log(f"📑 表格每页条数已调整为: {val} 条/页")

    def build_treeview_structure(self):
        for child in self.table_inner.winfo_children():
            child.destroy()

        headers = self.template_cfg.get("headers", ["手机号", "客户姓名", "公司名称"])
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
        def on_saved(new_cfg):
            self.template_cfg = new_cfg
            self.build_treeview_structure()
            if self.df is not None:
                self.refresh_treeview()

        TemplateConfigDialog(self.root, on_save_callback=on_saved, log_callback=self.log)

    def open_safety_config_dialog(self):
        def on_saved(new_cfg):
            self.safety_cfg = new_cfg
            config.SAFETY_CONFIG.update(new_cfg)
            self.lbl_daily_counter.config(text=f"本日已发: {self.daily_added_count}/{self.safety_cfg['DAILY_MAX_LIMIT']}")

            if "PAGE_SIZE" in new_cfg and new_cfg["PAGE_SIZE"] != self.page_size:
                self.page_size = new_cfg["PAGE_SIZE"]
                self.cbo_ui_page_size.set(str(self.page_size))
                self.current_page = 1
                self.refresh_treeview()

        SafetyConfigDialog(self.root, on_save_callback=on_saved, log_callback=self.log)

    def open_calibration_dialog(self):
        CalibrationDialog(self.root, bot_instance=self.bot, log_callback=self.log)

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

            success_phones = load_success_phones()
            history_matched_count = 0
            for idx_row, row in df.iterrows():
                p = str(row[phone_col]).strip()
                if p in success_phones and str(row["状态"]).strip() in ["未添加", "nan", ""]:
                    df.at[idx_row, "状态"] = "已发送申请(历史)"
                    history_matched_count += 1

            dedup_setting = self.template_cfg.get("dedup_cols", ["手机号"])
            valid_dedup_cols = [c for c in dedup_setting if c in df.columns]

            before_count = len(df)
            if valid_dedup_cols:
                df = df.drop_duplicates(subset=valid_dedup_cols, keep="first").reset_index(drop=True)
            after_count = len(df)
            removed_count = before_count - after_count

            with self.df_lock:
                self.df = df
                self.current_excel_path = path
                self.current_page = 1
                self.selected_indices.clear()
                self.all_selected = False

            self.tree.heading("勾选", text="[  ] 全选")
            self.lbl_selected_summary.config(text="已勾选: 0 项")
            self.refresh_treeview()

            dedup_msg = f"，依 [{'+'.join(valid_dedup_cols)}] 组合自动过滤重复记录 {removed_count} 条，剩余有效数据 {after_count} 条。" if removed_count > 0 else "。"
            hist_msg = f"（其中已包含历史成功发送手机号 {history_matched_count} 条）" if history_matched_count > 0 else ""
            self.log(f"✅ 成功载入数据: {os.path.basename(path)}{dedup_msg}{hist_msg}")
        except Exception as e:
            self.log(f"❌ 导入失败: {e}")

    def export_excel_template(self):
        headers = self.template_cfg.get("headers", ["手机号", "客户姓名", "公司名称"])
        time_str = time.strftime("%Y%m%d_%H%M%S")
        default_tpl_name = f"微信添加好友导入模板_{time_str}.xlsx"

        path = filedialog.asksaveasfilename(
            title="保存自定义模板文件",
            defaultextension=".xlsx",
            initialfile=default_tpl_name,
            filetypes=[("Excel", "*.xlsx")]
        )
        if not path:
            return

        demo_row = {}
        for h in headers:
            if h == self.template_cfg.get("phone_col"):
                demo_row[h] = "13800000000"
            elif "名" in h or "客户" in h:
                demo_row[h] = "张三"
            elif "司" in h or "机构" in h:
                demo_row[h] = "极客科技"
            else:
                demo_row[h] = "示例数据"

        tpl_df = pd.DataFrame([demo_row])
        try:
            tpl_df.to_excel(path, index=False)
            self.log(f"📄 模板文件已生成导出: {path}")
            messagebox.showinfo("成功", f"模板文件已成功导出至:\n{path}\n\n请按模板列名填入数据后点击【导入 Excel】。")
        except Exception as e:
            messagebox.showerror("导出失败", f"无法保存模板文件: {e}")

    def export_excel_file(self):
        with self.df_lock:
            if self.df is None or self.df.empty:
                messagebox.showinfo("提示", "当前无数据可导出！")
                return
            df_copy = self.df.copy()

        time_str = time.strftime("%Y%m%d_%H%M%S")
        default_filename = f"微信添加执行结果_{time_str}.xlsx"

        path = filedialog.asksaveasfilename(
            title="导出执行结果",
            defaultextension=".xlsx",
            initialfile=default_filename,
            filetypes=[("Excel", "*.xlsx")]
        )
        if path:
            try:
                df_copy.to_excel(path, index=False)
                messagebox.showinfo("导出成功", f"执行结果已成功导出保存至:\n{path}")
                self.log(f"💾 执行结果已导出保存: {path}")
            except Exception as e:
                messagebox.showerror("导出失败", f"导出文件时发生异常: {e}")

    def toggle_select_all(self):
        with self.df_lock:
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
        if region != "cell" or self.tree.identify_column(event.x) != "#1":
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

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_treeview(keep_page=True)

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.refresh_treeview(keep_page=True)

    def update_page_info(self):
        with self.df_lock:
            total_records = len(self.df) if self.df is not None else 0
        self.total_pages = max(1, (total_records + self.page_size - 1) // self.page_size)
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

    def refresh_treeview(self, keep_page=False):
        for btn in self.row_buttons.values():
            btn.destroy()
        self.row_buttons.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.update_page_info()
        with self.df_lock:
            if self.df is None or self.df.empty:
                return
            start = (self.current_page - 1) * self.page_size
            end = min(start + self.page_size, len(self.df))
            headers = self.template_cfg.get("headers", ["手机号", "客户姓名", "公司名称"])
            page_slice = self.df.iloc[start:end].copy()

        for idx, row in page_slice.iterrows():
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
        with self.df_lock:
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

        with self.df_lock:
            if self.df is None or self.df.empty:
                messagebox.showwarning("提示", "请先导入数据！")
                return

            if not self.selected_indices:
                messagebox.showwarning("提示", "请勾选需要执行的行！")
                return

            phone_col = self.template_cfg.get("phone_col", "手机号")
            success_phones = load_success_phones()

            pending = []
            skipped_success_count = 0

            for i in sorted(list(self.selected_indices)):
                st = str(self.df.at[i, "状态"]).strip()
                phone = str(self.df.at[i, phone_col]).strip()

                if "成功" in st or "已是好友" in st or phone in success_phones:
                    skipped_success_count += 1
                    if phone in success_phones and "成功" not in st and "已是好友" not in st:
                        self.df.at[i, "状态"] = "已成功发送(已跳过)"
                    continue

                pending.append(i)

        if skipped_success_count > 0:
            self.log(f"ℹ️ 批量模式自动跳过已成功发送过的号码: {skipped_success_count} 个（可点击单行按钮手动补发）")
            self.refresh_treeview(keep_page=True)

        if not pending:
            messagebox.showinfo("提示", "勾选的条目均已成功发送申请或已是好友，批量已全部跳过！\n如需重新发送，可点击对应行的【单个添加】手动发送。")
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
            daily_limit = self.safety_cfg.get("DAILY_MAX_LIMIT", 100)
            if self.cancel_requested or self.daily_added_count >= daily_limit:
                if self.daily_added_count >= daily_limit:
                    self.log(f"🛑 已达到单日安全上限 {daily_limit} 人，停止批量操作。")
                break

            with self.df_lock:
                phone = str(self.df.at[idx, phone_col]).strip()

            self.log(f"👉 [{i+1}/{len(target_indices)}] 准备添加: {phone}")
            result = self._run_task_pipeline(idx)
            if any(k in result for k in ["频繁", "限制", "封禁"]):
                self.log("🚨 命中风控熔断，紧急挂起全部任务！")
                break
            if i < len(target_indices) - 1 and not self.cancel_requested:
                c_min = self.safety_cfg.get("MIN_COOLDOWN_SEC", 25)
                c_max = self.safety_cfg.get("MAX_COOLDOWN_SEC", 45)
                cooldown = random.randint(min(c_min, c_max), max(c_min, c_max))
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
        greeting_type = self.template_cfg.get("greeting_type", "manual")
        greeting_tpl = self.template_cfg.get("greeting_template", "")
        remark_tpl = self.template_cfg.get("remark_template", "")

        with self.df_lock:
            row_dict = {col: self.df.at[idx, col] for col in self.df.columns}
            phone = str(self.df.at[idx, phone_col]).strip()

            greeting = ""
            if greeting_type == "manual":
                greeting = parse_placeholders(greeting_tpl, row_dict)

            remark = parse_placeholders(remark_tpl, row_dict)

        self.reset_step_status()

        btn = self.row_buttons.get(idx)
        if btn:
            self.root.after(0, lambda: btn.set_state("disabled", text="执行中..."))

        result = self.bot.execute_add_pipeline(phone, remark_name=remark, custom_greeting=greeting)

        with self.df_lock:
            self.df.at[idx, "状态"] = result

        if "成功" in result:
            self.daily_added_count += 1
            record_success_phone(phone)
            self.log(f"📝 手机号 {phone} 已加入已发送申请成功库。")
            self.root.after(0, lambda: self.lbl_daily_counter.config(text=f"本日已发: {self.daily_added_count}/{self.safety_cfg['DAILY_MAX_LIMIT']}"))

        self.root.after(0, lambda: self._update_row_view(idx, result))
        return result

    def _update_row_view(self, idx: int, result: str):
        if self.tree.exists(idx):
            vals = list(self.tree.item(idx, "values"))
            vals[-2] = result
            self.tree.item(idx, values=vals)
        btn = self.row_buttons.get(idx)
        if btn:
            is_done = "成功" in result or "已是好友" in result or "已发送" in result
            btn.set_state("normal", text="✓ 完成" if is_done else "➕ 重试")
        self.update_button_positions()

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
