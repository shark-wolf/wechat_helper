import os
import time
import random
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font as tkfont
import pandas as pd
import pyperclip

import config
from config import (
    THEME, STEPS, ICON_PATH, GREETING_POOL,
    FIXED_HEADERS, FIXED_PHONE_COL,
    load_coords, load_template_config, load_success_phones, record_success_phone,
    load_safety_config
)
from wechat_bot import WeChatBot
from ui_components import ModernButton, parse_placeholders
from ui_dialog_template import TemplateConfigDialog
from ui_dialog_calibration import CalibrationDialog
from ui_dialog_safety import SafetyConfigDialog
from ui_dialog_cleaner import DataCleaningDialog

class WeChatAddApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PC微信半自动辅助添加工具")
        self.root.geometry("1900x1200")
        self.root.configure(bg=THEME["bg"])

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        if os.path.exists(ICON_PATH):
            try:
                self.root.iconbitmap(ICON_PATH)
            except Exception:
                pass

        self.df = None
        self.df_lock = threading.Lock()
        self.current_excel_path = None
        self.row_buttons = {}  # {idx: (btn_add, btn_del)}
        self.step_labels = {}
        self.daily_added_count = 0
        self.is_batch_running = False
        self.cancel_requested = False

        self.selected_indices = set()
        self.all_selected = False

        # 用于精确计算各列文本真实像素宽度的字体对象
        self.measure_font = tkfont.Font(family="Microsoft YaHei UI", size=9)
        self.header_font = tkfont.Font(family="Microsoft YaHei UI", size=9, weight="bold")

        # 列宽自适应控制字典
        self.col_base_widths = {}
        self.col_cur_widths = {}
        self.last_table_w = 0

        # 首列扩宽至 88px，确保 "[  ] 全选" 100% 完整展示
        self.col_w_chk = 88
        self.col_w_seq = 60
        self.col_w_op = 105

        self.template_cfg = load_template_config()
        self.safety_cfg = load_safety_config()
        config.SAFETY_CONFIG.update(self.safety_cfg)

        self.bot = WeChatBot(logger_callback=self.log, step_callback=self.set_step_status)

        self.setup_styles()
        self.create_widgets()

    def on_closing(self):
        if self.is_batch_running:
            if messagebox.askyesno("确认退出", "批量添加任务正在运行中，确定要中断任务并退出程序吗？"):
                self.cancel_requested = True
                self.log("🛑 正在中断后台任务并安全退出...")
                self.root.after(300, self._force_exit)
        else:
            self._force_exit()

    def _force_exit(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"), background="#F3F4F6", foreground=THEME["text_main"], relief="flat", padding=(4, 6))
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

        self.btn_cfg_template = ModernButton(top_inner, text="⚙ 招呼与备注规则配置", command=self.open_template_config_dialog, bg="#6366F1", hover_bg="#4F46E5")
        self.btn_cfg_template.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_cfg_safety = ModernButton(top_inner, text="\U0001f6e1 安全参数设置", command=self.open_safety_config_dialog, bg="#059669", hover_bg="#047857")
        self.btn_cfg_safety.pack(side=tk.LEFT, padx=(0, 15))

        self.btn_export = ModernButton(top_inner, text="💾 导出结果", command=self.export_excel_file, bg="#4B5563", hover_bg="#374151")
        self.btn_export.pack(side=tk.LEFT, padx=(0, 15))

        self.btn_batch_start = ModernButton(top_inner, text="▶ 批量安全执行", command=self.toggle_batch_execution, bg=THEME["primary"], hover_bg=THEME["primary_hover"])
        self.btn_batch_start.pack(side=tk.LEFT, padx=(0, 15))

        self.btn_calib = ModernButton(top_inner, text="🎯 坐标标定模式", command=self.open_calibration_dialog, bg="#6B7280", hover_bg="#4B5563")
        self.btn_calib.pack(side=tk.LEFT, padx=(0, 15))

        self.lbl_selected_summary = tk.Label(top_inner, text="已勾选: 0 项 (共 0 条)", fg="#2563EB", bg=THEME["card_bg"], font=("Microsoft YaHei UI", 9, "bold"))
        self.lbl_selected_summary.pack(side=tk.LEFT, padx=10)

        self.lbl_daily_counter = tk.Label(top_inner, text=f"本日已发: {self.daily_added_count}/{self.safety_cfg['DAILY_MAX_LIMIT']}", fg=THEME["text_main"], bg=THEME["card_bg"], font=("Microsoft YaHei UI", 9, "bold"))
        self.lbl_daily_counter.pack(side=tk.RIGHT, padx=5)

        # 表格卡片
        self.table_card = tk.Frame(self.root, bg=THEME["card_bg"], highlightbackground=THEME["border"], highlightthickness=1)
        self.table_card.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        self.table_inner = tk.Frame(self.table_card, bg=THEME["card_bg"], padx=10, pady=10)
        self.table_inner.pack(fill=tk.BOTH, expand=True)

        self.build_treeview_structure()

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

    def build_treeview_structure(self):
        for child in self.table_inner.winfo_children():
            child.destroy()

        self.tree_columns = ["勾选", "序号"] + FIXED_HEADERS + ["微信备注", "状态", "操作"]

        self.tree = ttk.Treeview(self.table_inner, columns=self.tree_columns, show="headings")
        self.tree.heading("勾选", text="[  ] 全选", command=self.toggle_select_all)
        self.tree.column("勾选", width=self.col_w_chk, stretch=False, anchor="center")

        self.tree.heading("序号", text="序号")
        self.tree.column("序号", width=self.col_w_seq, stretch=False, anchor="center")

        defaults = {
            "手机号": 125, "姓名": 95, "小区": 135, "楼栋": 90,
            "单元": 90, "房号": 90, "微信备注": 240, "状态": 140
        }
        for h in FIXED_HEADERS + ["微信备注", "状态"]:
            self.col_base_widths[h] = defaults.get(h, 110)
            self.col_cur_widths[h] = defaults.get(h, 110)
            self.tree.heading(h, text=h)
            self.tree.column(h, width=self.col_cur_widths[h], stretch=False, anchor="center")

        self.tree.heading("操作", text="操作")
        self.tree.column("操作", width=self.col_w_op, stretch=False, anchor="center")

        self.tree.bind("<ButtonRelease-1>", self.on_tree_cell_click)
        v_scrollbar = ttk.Scrollbar(self.table_inner, orient=tk.VERTICAL, command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(self.table_inner, orient=tk.HORIZONTAL, command=self._on_horizontal_scroll)

        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        self.table_inner.grid_rowconfigure(0, weight=1)
        self.table_inner.grid_columnconfigure(0, weight=1)

        self.table_inner.bind("<Configure>", self._on_table_configure)
        self.tree.bind("<Configure>", lambda e: self.update_button_positions())
        self.tree.bind("<MouseWheel>", lambda e: self.root.after(50, self.update_button_positions))

    def _calc_content_widths(self):
        """精准测量每列真实文本的像素宽度，实现完全自适应不截断"""
        with self.df_lock:
            if self.df is None or self.df.empty:
                return

            cols_to_calc = FIXED_HEADERS + ["微信备注", "状态"]
            for col in cols_to_calc:
                header_px = self.header_font.measure(str(col)) + 30
                max_px = header_px

                if col in self.df.columns:
                    for val in self.df[col].dropna().head(200):
                        s = str(val).strip()
                        if s and s not in ["nan", "-"]:
                            w_px = self.measure_font.measure(s) + 26
                            if w_px > max_px:
                                max_px = w_px

                if col == "手机号":
                    calc_w = max(125, max_px)
                elif col == "微信备注":
                    calc_w = max(220, min(550, max_px))
                elif col == "状态":
                    calc_w = max(135, min(300, max_px))
                elif col == "小区":
                    calc_w = max(130, min(350, max_px))
                else:
                    calc_w = max(85, min(220, max_px))

                self.col_base_widths[col] = calc_w
                self.col_cur_widths[col] = calc_w

    def _on_table_configure(self, event=None):
        """主界面大小缩放时自适应重算，确保充分铺满视口不留右侧断层"""
        if event is not None and hasattr(event, "width"):
            cur_w = event.width
        else:
            cur_w = self.table_inner.winfo_width()

        avail_w = cur_w - 24
        if avail_w <= 200 or abs(avail_w - self.last_table_w) < 6:
            return
        self.last_table_w = avail_w

        cols = FIXED_HEADERS + ["微信备注", "状态"]
        base_total = self.col_w_chk + self.col_w_seq + sum(self.col_base_widths.get(c, 110) for c in cols) + self.col_w_op

        if avail_w > base_total:
            extra = avail_w - base_total
            num_cols = len(cols)
            add_per_col = extra // num_cols
            rem = extra % num_cols
            for idx, c in enumerate(cols):
                add_w = add_per_col + (1 if idx < rem else 0)
                self.col_cur_widths[c] = self.col_base_widths[c] + add_w
        else:
            for c in cols:
                self.col_cur_widths[c] = self.col_base_widths[c]

        for c in cols:
            self.tree.column(c, width=self.col_cur_widths[c])

        self.update_button_positions()

    def _on_horizontal_scroll(self, *args):
        self.tree.xview(*args)
        self.update_button_positions()

    def open_template_config_dialog(self):
        def on_saved(new_cfg):
            self.template_cfg = new_cfg
            with self.df_lock:
                if self.df is not None and not self.df.empty:
                    remark_tpl = self.template_cfg.get("remark_template", "")
                    self.df["微信备注"] = self.df.apply(lambda r: parse_placeholders(remark_tpl, r.to_dict()), axis=1)
            self._calc_content_widths()
            self.refresh_treeview()

        TemplateConfigDialog(self.root, on_save_callback=on_saved, log_callback=self.log)

    def open_safety_config_dialog(self):
        def on_saved(new_cfg):
            self.safety_cfg = new_cfg
            config.SAFETY_CONFIG.update(new_cfg)
            self.lbl_daily_counter.config(text=f"本日已发: {self.daily_added_count}/{self.safety_cfg['DAILY_MAX_LIMIT']}")

        SafetyConfigDialog(self.root, on_save_callback=on_saved, log_callback=self.log)

    def open_calibration_dialog(self):
        CalibrationDialog(self.root, bot_instance=self.bot, log_callback=self.log)

    def import_excel_file(self):
        path = filedialog.askopenfilename(title="选择 Excel 文件", filetypes=[("Excel", "*.xlsx *.xls"), ("All", "*.*")])
        if not path:
            return
        try:
            raw_df = pd.read_excel(path, header=None, dtype=str)
            if raw_df.empty:
                messagebox.showwarning("提示", "所选 Excel 文件中无数据！")
                return

            DataCleaningDialog(
                self.root,
                raw_df=raw_df,
                file_path=path,
                on_confirm_callback=lambda cleaned_df: self._apply_cleaned_data(cleaned_df, path),
                log_callback=self.log
            )
        except Exception as e:
            self.log(f"❌ 读取 Excel 文件异常: {e}")
            messagebox.showerror("读取失败", f"无法解析该 Excel 文件：\n{e}")

    def _apply_cleaned_data(self, cleaned_df: pd.DataFrame, path: str):
        df = cleaned_df.copy()

        if "状态" not in df.columns:
            df["状态"] = "未添加"

        remark_tpl = self.template_cfg.get("remark_template", "")
        df["微信备注"] = df.apply(lambda r: parse_placeholders(remark_tpl, r.to_dict()), axis=1)

        success_phones = load_success_phones()
        history_matched_count = 0
        for idx_row, row in df.iterrows():
            p = str(row[FIXED_PHONE_COL]).strip()
            if p in success_phones and str(row["状态"]).strip() in ["未添加", "nan", ""]:
                df.at[idx_row, "状态"] = "已发送申请(历史)"
                history_matched_count += 1

        dedup_setting = self.template_cfg.get("dedup_cols", FIXED_HEADERS)
        valid_dedup_cols = [c for c in dedup_setting if c in df.columns]

        before_count = len(df)
        if valid_dedup_cols:
            df = df.drop_duplicates(subset=valid_dedup_cols, keep="first").reset_index(drop=True)
        after_count = len(df)
        removed_count = before_count - after_count

        with self.df_lock:
            self.df = df
            self.current_excel_path = path
            self.selected_indices.clear()
            self.all_selected = False

        self._calc_content_widths()
        self.tree.heading("勾选", text="[  ] 全选")
        self.refresh_treeview()

        # 安全触发自适应重布局
        self.root.after(50, self._on_table_configure)

        dedup_msg = f"，依 [{'+'.join(valid_dedup_cols)}] 组合自动去重 {removed_count} 条，剩余有效数据 {after_count} 条。" if removed_count > 0 else "。"
        hist_msg = f"（其中已包含历史成功发送手机号 {history_matched_count} 条）" if history_matched_count > 0 else ""
        self.log(f"✅ 成功清洗并导入数据: {os.path.basename(path)}{dedup_msg}{hist_msg}")

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

        self.update_summary_label()
        self.refresh_treeview()

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
        self.update_summary_label()

    def update_summary_label(self):
        with self.df_lock:
            total_records = len(self.df) if self.df is not None else 0
        self.lbl_selected_summary.config(text=f"已勾选: {len(self.selected_indices)} 项 (共 {total_records} 条)")

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

    def refresh_treeview(self):
        for btns in self.row_buttons.values():
            for b in btns:
                b.destroy()
        self.row_buttons.clear()

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.update_summary_label()
        with self.df_lock:
            if self.df is None or self.df.empty:
                return
            all_rows = self.df.copy()

        cols = FIXED_HEADERS + ["微信备注", "状态"]
        for c in cols:
            self.tree.column(c, width=self.col_cur_widths.get(c, 110))

        remark_tpl = self.template_cfg.get("remark_template", "")

        for idx, row in all_rows.iterrows():
            chk_char = "[√]" if idx in self.selected_indices else "[  ]"

            row_vals = [chk_char, idx + 1]
            for h in FIXED_HEADERS:
                val = str(row[h]).strip() if h in row and pd.notna(row[h]) else "-"
                row_vals.append(val)

            remark_val = str(row["微信备注"]).strip() if "微信备注" in row and pd.notna(row["微信备注"]) else parse_placeholders(remark_tpl, row.to_dict())
            row_vals.append(remark_val)

            status_val = str(row["状态"]) if "状态" in row and pd.notna(row["状态"]) else "未添加"
            row_vals.append(status_val)
            row_vals.append("")

            self.tree.insert("", tk.END, iid=idx, values=row_vals)

            btn_add = ModernButton(
                self.tree,
                text="➕",
                command=lambda i=idx: self.start_single_task(i),
                padx=0,
                pady=0,
                font=("Segoe UI Symbol", 10, "bold")
            )
            btn_del = ModernButton(
                self.tree,
                text="\U0001f5d1",
                bg="#EF4444",
                hover_bg="#DC2626",
                command=lambda i=idx: self.delete_row(i),
                padx=0,
                pady=0,
                font=("Segoe UI Emoji", 10)
            )
            self.row_buttons[idx] = (btn_add, btn_del)

        self.root.after(100, self.update_button_positions)

    def update_button_positions(self):
        """精准计算按钮摆放位置：➕ 与 🗑️ 之间添加清晰的 margin 间距（14px）"""
        with self.df_lock:
            if self.df is None or self.df.empty:
                return
        for idx, btns in self.row_buttons.items():
            btn_add, btn_del = btns
            bbox = self.tree.bbox(idx, column="操作")
            if bbox and len(bbox) == 4:
                x, y, w, h = bbox
                btn_size = 24
                btn_margin = 14
                total_w = btn_size * 2 + btn_margin

                start_x = x + max(4, (w - total_w) // 2)
                btn_y = y + max(1, (h - btn_size) // 2)

                btn_add.place(x=start_x, y=btn_y, width=btn_size, height=btn_size)
                btn_del.place(x=start_x + btn_size + btn_margin, y=btn_y, width=btn_size, height=btn_size)
            else:
                btn_add.place_forget()
                btn_del.place_forget()

    def delete_row(self, idx: int):
        if self.is_batch_running:
            messagebox.showwarning("操作冲突", "批量添加任务正在执行中，请先停止任务后再删除数据！")
            return

        with self.df_lock:
            phone_num = str(self.df.at[idx, FIXED_PHONE_COL]).strip() if idx in self.df.index else ""

        if not messagebox.askyesno("删除确认", f"确定要删除序号【{idx + 1}】(号码: {phone_num}) 的数据吗？"):
            return

        with self.df_lock:
            self.df = self.df.drop(index=idx).reset_index(drop=True)
            new_selected = set()
            for s_idx in self.selected_indices:
                if s_idx < idx:
                    new_selected.add(s_idx)
                elif s_idx > idx:
                    new_selected.add(s_idx - 1)
            self.selected_indices = new_selected

        self.refresh_treeview()
        self.log(f"🗑️ 已成功删除序号【{idx + 1}】(号码: {phone_num}) 的记录。")

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

            success_phones = load_success_phones()
            pending = []
            skipped_success_count = 0

            for i in sorted(list(self.selected_indices)):
                st = str(self.df.at[i, "状态"]).strip()
                phone = str(self.df.at[i, FIXED_PHONE_COL]).strip()

                if "成功" in st or "已是好友" in st or phone in success_phones:
                    skipped_success_count += 1
                    if phone in success_phones and "成功" not in st and "已是好友" not in st:
                        self.df.at[i, "状态"] = "已成功发送(已跳过)"
                    continue

                pending.append(i)

        if skipped_success_count > 0:
            self.log(f"ℹ️ 批量模式自动跳过已成功发送过的号码: {skipped_success_count} 个（可点击单行 ➕ 按钮手动补发）")
            self.refresh_treeview()

        if not pending:
            messagebox.showinfo("提示", "勾选的条目均已成功发送申请或已是好友，批量已全部跳过！\n如需重新发送，可点击对应行的【➕】图标手动发送。")
            return

        self.log(f"📋 执行模式：执行【勾选指定项】，待处理: {len(pending)} 个")

        self.is_batch_running = True
        self.cancel_requested = False
        self.btn_batch_start.set_state("normal", text="⏹ 停止批量任务", bg=THEME["warning"])
        threading.Thread(target=self._run_batch_worker, args=(pending,), daemon=True).start()

    def _run_batch_worker(self, target_indices):
        self.log(f"🛡️ 启动批量调度，总计: {len(target_indices)} 个任务")
        for i, idx in enumerate(target_indices):
            daily_limit = self.safety_cfg.get("DAILY_MAX_LIMIT", 100)
            if self.cancel_requested or self.daily_added_count >= daily_limit:
                if self.daily_added_count >= daily_limit:
                    self.log(f"🛑 已达到单日安全上限 {daily_limit} 人，停止批量操作。")
                break

            with self.df_lock:
                phone = str(self.df.at[idx, FIXED_PHONE_COL]).strip()

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
        greeting_type = self.template_cfg.get("greeting_type", "manual")
        greeting_tpl = self.template_cfg.get("greeting_template", "")
        remark_tpl = self.template_cfg.get("remark_template", "")

        with self.df_lock:
            row_dict = {col: self.df.at[idx, col] for col in self.df.columns}
            phone = str(self.df.at[idx, FIXED_PHONE_COL]).strip()

            if greeting_type == "manual":
                greeting = parse_placeholders(greeting_tpl, row_dict)
            else:
                pool = self.template_cfg.get("greetings", GREETING_POOL)
                if not pool:
                    pool = GREETING_POOL
                greeting = random.choice(pool)

            remark = parse_placeholders(remark_tpl, row_dict)
            self.df.at[idx, "微信备注"] = remark

        self.reset_step_status()

        btns = self.row_buttons.get(idx)
        if btns:
            btn_add, _ = btns
            self.root.after(0, lambda: btn_add.set_state("disabled", text="⏳"))

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
        btns = self.row_buttons.get(idx)
        if btns:
            btn_add, _ = btns
            is_done = "成功" in result or "已是好友" in result or "已发送" in result
            btn_add.set_state("normal", text="✓" if is_done else "➕")
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
                menu.add_command(label="复制选中内容", command=lambda pyperclip=pyperclip: pyperclip.copy(sel_text))
        except Exception:
            pass

        if not has_sel:
            try:
                line_idx = self.log_text.index(f"@{event.x},{event.y} linestart")
                line_end = self.log_text.index(f"@{event.x},{event.y} lineend")
                line_content = self.log_text.get(line_idx, line_end).strip()
                if line_content:
                    menu.add_command(label="复制当前行", command=lambda pyperclip=pyperclip: pyperclip.copy(line_content))
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
