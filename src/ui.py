import os
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyperclip

import config
from config import THEME, STEPS, ICON_PATH, FIXED_PHONE_COL, load_coords, load_template_config, load_safety_config
from wechat_bot import WeChatBot
from ui_components import ModernButton
from ui_table_view import ContactTableView
from data_service import DataService
from batch_scheduler import BatchScheduler
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

        self.template_cfg = load_template_config()
        self.safety_cfg = load_safety_config()
        config.SAFETY_CONFIG.update(self.safety_cfg)

        self.step_labels = {}
        self.daily_added_count = 0
        self.search_phone_kw = tk.StringVar(value="")

        self.bot = WeChatBot(logger_callback=self.log, step_callback=self.set_step_status)
        self.scheduler = BatchScheduler(
            bot=self.bot,
            log_callback=self.log,
            step_callback=self.set_step_status,
            status_callback=self._on_row_status_updated,
            counter_callback=self._on_count_incremented,
            get_count_callback=lambda: self.daily_added_count
        )

        self.setup_styles()
        self.create_widgets()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"), background="#F3F4F6", foreground=THEME["text_main"], relief="flat", padding=(4, 6))
        style.configure("Treeview", font=("Microsoft YaHei UI", 9), background="white", fieldbackground="white", foreground=THEME["text_main"], rowheight=34, bordercolor=THEME["border"], borderwidth=1)
        style.map("Treeview", background=[("selected", "#E0F2FE")], foreground=[("selected", "#0369A1")])
        style.configure("Vertical.TScrollbar", gripcount=0, background="#D1D5DB", troughcolor="#F3F4F6", borderwidth=0, arrowsize=12)

    def create_widgets(self):
        # 1. 顶部操作栏
        top_card = tk.Frame(self.root, bg=THEME["card_bg"], highlightbackground=THEME["border"], highlightthickness=1)
        top_card.pack(fill=tk.X, padx=15, pady=(15, 8))
        top_inner = tk.Frame(top_card, bg=THEME["card_bg"], padx=15, pady=12)
        top_inner.pack(fill=tk.X)

        ModernButton(top_inner, text="📁 导入 Excel", command=self.import_excel_file, bg=THEME["accent"], hover_bg=THEME["accent_hover"]).pack(side=tk.LEFT, padx=(0, 8))
        ModernButton(top_inner, text="⚙ 招呼与备注规则配置", command=self.open_template_dialog, bg="#6366F1", hover_bg="#4F46E5").pack(side=tk.LEFT, padx=(0, 8))
        ModernButton(top_inner, text="\U0001f6e1 安全参数设置", command=self.open_safety_dialog, bg="#059669", hover_bg="#047857").pack(side=tk.LEFT, padx=(0, 15))
        ModernButton(top_inner, text="💾 导出结果", command=self.export_excel_file, bg="#4B5563", hover_bg="#374151").pack(side=tk.LEFT, padx=(0, 15))

        self.btn_batch = ModernButton(top_inner, text="▶ 批量安全执行", command=self.toggle_batch_execution, bg=THEME["primary"], hover_bg=THEME["primary_hover"])
        self.btn_batch.pack(side=tk.LEFT, padx=(0, 15))

        ModernButton(top_inner, text="🎯 坐标标定模式", command=lambda: CalibrationDialog(self.root, self.bot, self.log), bg="#6B7280", hover_bg="#4B5563").pack(side=tk.LEFT, padx=(0, 15))

        # 手机号过滤搜索框
        search_f = tk.Frame(top_inner, bg="#F3F4F6", highlightbackground=THEME["border"], highlightthickness=1, padx=6, pady=2)
        search_f.pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(search_f, text="🔍 手机号:", font=("Microsoft YaHei UI", 9, "bold"), bg="#F3F4F6", fg=THEME["text_main"]).pack(side=tk.LEFT, padx=(2, 4))
        ent = tk.Entry(search_f, textvariable=self.search_phone_kw, font=("Consolas", 10), width=15, relief=tk.FLAT, bg="white")
        ent.pack(side=tk.LEFT, ipady=3, padx=(0, 4))
        ent.bind("<KeyRelease>", lambda e: self.table_view.set_search_keyword(self.search_phone_kw.get()))

        btn_clear = tk.Label(search_f, text="✕", font=("Microsoft YaHei UI", 9, "bold"), fg="#9CA3AF", bg="#F3F4F6", cursor="hand2")
        btn_clear.pack(side=tk.LEFT, padx=3)
        btn_clear.bind("<Button-1>", lambda e: (self.search_phone_kw.set(""), self.table_view.set_search_keyword("")))

        self.lbl_selected = tk.Label(top_inner, text="已勾选: 0 项 (共 0 条)", fg="#2563EB", bg=THEME["card_bg"], font=("Microsoft YaHei UI", 9, "bold"))
        self.lbl_selected.pack(side=tk.LEFT, padx=8)

        self.lbl_counter = tk.Label(top_inner, text=f"本日已发: {self.daily_added_count}/{self.safety_cfg['DAILY_MAX_LIMIT']}", fg=THEME["text_main"], bg=THEME["card_bg"], font=("Microsoft YaHei UI", 9, "bold"))
        self.lbl_counter.pack(side=tk.RIGHT, padx=5)

        # 2. 中部数据表格组件
        table_card = tk.Frame(self.root, bg=THEME["card_bg"], highlightbackground=THEME["border"], highlightthickness=1)
        table_card.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        table_inner = tk.Frame(table_card, bg=THEME["card_bg"], padx=10, pady=10)
        table_inner.pack(fill=tk.BOTH, expand=True)

        self.table_view = ContactTableView(
            table_inner,
            on_single_add=self.start_single_task,
            on_delete_row=self.delete_row,
            on_selection_changed=self._on_table_selection_changed
        )
        self.table_view.pack(fill=tk.BOTH, expand=True)

        # 3. 操作状态流转指示卡片
        flow_card = tk.LabelFrame(self.root, text="  操作执行实时状态  ", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"], highlightbackground=THEME["border"], highlightthickness=1, padx=15, pady=6)
        flow_card.pack(fill=tk.X, padx=15, pady=6)
        for key, desc in STEPS:
            item = tk.Frame(flow_card, bg=THEME["card_bg"])
            item.pack(fill=tk.X, pady=1)
            tk.Label(item, text=desc, font=("Microsoft YaHei UI", 9), fg=THEME["text_main"], bg=THEME["card_bg"]).pack(side=tk.LEFT)
            lbl = tk.Label(item, text="等待中", font=("Microsoft YaHei UI", 9, "bold"), fg="#9CA3AF", bg=THEME["card_bg"], width=14, anchor="e")
            lbl.pack(side=tk.RIGHT)
            self.step_labels[key] = lbl

        # 4. 底部日志控制台
        log_card = tk.LabelFrame(self.root, text="  安全运行控制台日志 (双击行复制 / 右键菜单)  ", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"], highlightbackground=THEME["border"], highlightthickness=1, padx=10, pady=6, height=240)
        log_card.pack_propagate(False)
        log_card.pack(fill=tk.X, padx=15, pady=(6, 15))

        self.log_text = tk.Text(log_card, wrap=tk.WORD, state=tk.DISABLED, bg="#111827", fg="#F3F4F6", font=("Consolas", 9), relief=tk.FLAT, padx=8, pady=6)
        scroll = ttk.Scrollbar(log_card, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text.bind("<Double-1>", self._on_log_double_click)
        self.log_text.bind("<Button-3>", self._show_log_context_menu)

    def import_excel_file(self):
        path = filedialog.askopenfilename(title="选择 Excel 文件", filetypes=[("Excel 文件 (*.xlsx;*.xls)", "*.xlsx *.xls"), ("所有文件 (*.*)", "*.*")])
        if not path:
            return
        try:
            raw_df = DataService.read_excel_file(path)
            if raw_df.empty:
                messagebox.showwarning("提示", "所选 Excel 文件中无数据！")
                return
            DataCleaningDialog(self.root, raw_df=raw_df, file_path=path, on_confirm_callback=lambda c_df: self._apply_cleaned_data(c_df, path), log_callback=self.log)
        except Exception as e:
            self.log(f"❌ 读取 Excel 文件异常: {e}")
            messagebox.showerror("读取失败", f"无法解析该 Excel 文件：\n{e}")

    def _apply_cleaned_data(self, cleaned_df, path):
        df, dedup_removed, hist_count = DataService.process_imported_data(cleaned_df, self.template_cfg)
        self.table_view.set_data(df)
        self.search_phone_kw.set("")
        dedup_info = f"，自动去重 {dedup_removed} 条" if dedup_removed > 0 else ""
        hist_info = f"（已匹配历史成功 {hist_count} 条）" if hist_count > 0 else ""
        self.log(f"✅ 成功清洗并导入数据: {os.path.basename(path)}{dedup_info}{hist_info}")

    def export_excel_file(self):
        if self.table_view.df is None or self.table_view.df.empty:
            messagebox.showinfo("提示", "当前无数据可导出！")
            return
        path = filedialog.asksaveasfilename(title="导出执行结果", defaultextension=".xlsx", initialfile=f"微信添加结果_{time.strftime('%Y%m%d_%H%M%S')}.xlsx", filetypes=[("Excel", "*.xlsx")])
        if path:
            DataService.export_excel(self.table_view.df, path)
            self.log(f"💾 执行结果已导出保存: {path}")
            messagebox.showinfo("导出成功", f"执行结果已保存至:\n{path}")

    def start_single_task(self, idx: int):
        if self.scheduler.is_running:
            messagebox.showwarning("冲突", "批量任务正在执行中！")
            return
        self.reset_step_status()
        row_dict = self.table_view.df.loc[idx].to_dict()
        self.scheduler.run_single(idx, row_dict, self.template_cfg)

    def toggle_batch_execution(self):
        if self.scheduler.is_running:
            self.scheduler.request_stop()
            self.btn_batch.set_state("disabled", text="正在停止...")
            return

        if self.table_view.df is None or self.table_view.df.empty or not self.table_view.selected_indices:
            messagebox.showwarning("提示", "请先导入数据并勾选执行条目！")
            return

        pending = []
        for i in sorted(list(self.table_view.selected_indices)):
            st = str(self.table_view.df.at[i, "状态"]).strip()
            if not any(k in st for k in ["成功", "已是好友"]):
                pending.append(i)

        if not pending:
            messagebox.showinfo("提示", "勾选项目均已添加或无需处理！")
            return

        self.btn_batch.set_state("normal", text="⏹ 停止批量任务", bg=THEME["warning"])
        self.scheduler.run_batch(
            target_indices=pending,
            get_record_func=lambda i: self.table_view.df.loc[i].to_dict(),
            template_cfg=self.template_cfg,
            safety_cfg=self.safety_cfg,
            on_finished=lambda: self.root.after(0, lambda: self.btn_batch.set_state("normal", text="▶ 批量安全执行", bg=THEME["primary"]))
        )

    def delete_row(self, idx: int):
        if self.scheduler.is_running:
            messagebox.showwarning("冲突", "任务进行中不可删除行！")
            return
        phone = str(self.table_view.df.at[idx, FIXED_PHONE_COL]).strip()
        if messagebox.askyesno("删除确认", f"确定删除行序号【{idx + 1}】({phone}) 吗？"):
            df = self.table_view.df.drop(index=idx).reset_index(drop=True)
            self.table_view.set_data(df)
            self.log(f"🗑️ 已删除序号【{idx + 1}】({phone}) 记录。")

    def _on_row_status_updated(self, idx, remark, result):
        self.root.after(0, lambda: self.table_view.update_row_status(idx, remark, result))

    def _on_count_incremented(self, phone):
        self.daily_added_count += 1
        self.log(f"📝 手机号 {phone} 已加入已发送申请成功库。")
        self.root.after(0, lambda: self.lbl_counter.config(text=f"本日已发: {self.daily_added_count}/{self.safety_cfg['DAILY_MAX_LIMIT']}"))

    def _on_table_selection_changed(self, visible_count, total_count, selected_count):
        kw = self.search_phone_kw.get().strip()
        txt = f"已勾选: {selected_count} 项 (当前筛选: {visible_count}/{total_count} 条)" if kw else f"已勾选: {selected_count} 项 (共 {total_count} 条)"
        self.lbl_selected.config(text=txt)

    def open_template_dialog(self):
        TemplateConfigDialog(self.root, on_save_callback=lambda cfg: (setattr(self, "template_cfg", cfg), self.table_view.calc_optimal_widths(), self.table_view.refresh()), log_callback=self.log)

    def open_safety_dialog(self):
        def _save(cfg):
            self.safety_cfg = cfg
            config.SAFETY_CONFIG.update(cfg)
            self.lbl_counter.config(text=f"本日已发: {self.daily_added_count}/{self.safety_cfg['DAILY_MAX_LIMIT']}")
        SafetyConfigDialog(self.root, on_save_callback=_save, log_callback=self.log)

    def set_step_status(self, step_key, status, color="#9CA3AF"):
        self.root.after(0, lambda: self.step_labels[step_key].config(text=status, fg=color) if step_key in self.step_labels else None)

    def reset_step_status(self):
        for key, _ in STEPS:
            self.set_step_status(key, "等待中", "#9CA3AF")

    def log(self, message: str):
        self.root.after(0, lambda: (self.log_text.config(state=tk.NORMAL), self.log_text.insert(tk.END, time.strftime("[%H:%M:%S] ") + message + "\n"), self.log_text.see(tk.END), self.log_text.config(state=tk.DISABLED)))

    def _on_log_double_click(self, event):
        try:
            line = self.log_text.get(self.log_text.index(f"@{event.x},{event.y} linestart"), self.log_text.index(f"@{event.x},{event.y} lineend")).strip()
            if line:
                pyperclip.copy(line)
        except Exception:
            pass

    def _show_log_context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="复制全部日志", command=lambda: pyperclip.copy(self.log_text.get("1.0", tk.END).strip()))
        menu.add_command(label="查看有效相对坐标", command=lambda: messagebox.showinfo("坐标配置", str(load_coords())))
        menu.add_separator()
        menu.add_command(label="清空日志控制台", command=lambda: (self.log_text.config(state=tk.NORMAL), self.log_text.delete("1.0", tk.END), self.log_text.config(state=tk.DISABLED)))
        menu.post(event.x_root, event.y_root)

    def on_closing(self):
        if self.scheduler.is_running:
            if messagebox.askyesno("确认退出", "任务正在执行中，确定退出吗？"):
                self.scheduler.request_stop()
                self.root.after(200, lambda: os._exit(0))
        else:
            os._exit(0)
