import re
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from config import THEME, FIXED_HEADERS, FIXED_PHONE_COL
from ui_components import ModernButton

def clean_phone_number(raw_val) -> str:
    """清洗手机号：提取所有纯数字，并仅保留前 11 位数字"""
    if pd.isna(raw_val) or raw_val is None:
        return ""
    s = str(raw_val).strip()
    if s.startswith("+86"):
        s = s[3:]
    elif s.startswith("86") and len(s) > 11:
        s = s[2:]
    digits = re.sub(r"\D", "", s)
    return digits[:11] if len(digits) >= 11 else digits

def format_building_and_unit(field_name: str, raw_val: str) -> str:
    """若楼栋和单元是纯数字，自动追加对应中文单位"""
    if not raw_val:
        return ""
    s = str(raw_val).strip()
    if field_name == "楼栋":
        if s.isdigit():
            return f"{s}栋"
    elif field_name == "单元":
        if s.isdigit():
            return f"{s}单元"
    return s

class MissingHeadersInputDialog(tk.Toplevel):
    """为未在数据列中提取到的目标表头提供统一默认值的弹窗"""
    def __init__(self, parent, missing_headers: list, on_confirm_callback):
        super().__init__(parent)
        self.title("补全未提取列数据")
        dlg_w, dlg_h = 520, 180 + len(missing_headers) * 55
        self.geometry(f"{dlg_w}x{dlg_h}")
        self.resizable(False, False)
        self.configure(bg=THEME["card_bg"])
        self.transient(parent)
        self.grab_set()

        root_x, root_y = parent.winfo_x(), parent.winfo_y()
        root_w, root_h = parent.winfo_width(), parent.winfo_height()
        pos_x = root_x + max(0, (root_w - dlg_w) // 2)
        pos_y = root_y + max(0, (root_h - dlg_h) // 2)
        self.geometry(f"{dlg_w}x{dlg_h}+{pos_x}+{pos_y}")

        self.missing_headers = missing_headers
        self.on_confirm_callback = on_confirm_callback
        self.entries = {}

        self._create_widgets()

    def _create_widgets(self):
        head_f = tk.Frame(self, bg=THEME["card_bg"], padx=20, pady=12)
        head_f.pack(fill=tk.X)
        tk.Label(head_f, text="⚠️ 以下目标列未在数据列表中提取到数据：", font=("Microsoft YaHei UI", 10, "bold"), fg="#D97706", bg=THEME["card_bg"]).pack(anchor="w")
        tk.Label(head_f, text="请输入用于填充对应列的统一输出值（如固定小区名、单元等）：", font=("Microsoft YaHei UI", 8), fg=THEME["text_sub"], bg=THEME["card_bg"]).pack(anchor="w", pady=(3, 0))

        content_f = tk.Frame(self, bg=THEME["card_bg"], padx=25)
        content_f.pack(fill=tk.BOTH, expand=True)

        for h in self.missing_headers:
            row_f = tk.Frame(content_f, bg=THEME["card_bg"])
            row_f.pack(fill=tk.X, pady=6)

            tag_lbl = tk.Label(row_f, text=f"【{h}】输出值:", font=("Microsoft YaHei UI", 9, "bold"), width=15, anchor="e", bg=THEME["card_bg"], fg=THEME["text_main"])
            tag_lbl.pack(side=tk.LEFT)

            ent = tk.Entry(row_f, font=("Microsoft YaHei UI", 9), relief=tk.SOLID, bd=1)
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0), ipady=3)
            self.entries[h] = ent

        btn_row = tk.Frame(self, bg=THEME["card_bg"], padx=20, pady=12)
        btn_row.pack(fill=tk.X, side="bottom")

        ModernButton(btn_row, text="确认并完成导入", command=self.on_confirm, bg=THEME["primary"], hover_bg=THEME["primary_hover"]).pack(side=tk.RIGHT, padx=5)
        ModernButton(btn_row, text="返回修改", command=self.destroy, bg="#E5E7EB", hover_bg="#D1D5DB", fg="#374151").pack(side=tk.RIGHT, padx=5)

    def on_confirm(self):
        values = {}
        for h, ent in self.entries.items():
            val = ent.get().strip()
            if h == FIXED_PHONE_COL:
                val = clean_phone_number(val)
                if len(val) < 11:
                    messagebox.showerror("提示", "【手机号】需为有效的前 11 位数字！请重新输入。")
                    return
            elif h in ["楼栋", "单元"]:
                val = format_building_and_unit(h, val)
            values[h] = val

        self.destroy()
        if self.on_confirm_callback:
            self.on_confirm_callback(values)


class DataCleaningDialog(tk.Toplevel):
    """Excel 纯数据清洗与列映射提取窗口（全自适应宽度与规整排版）"""
    def __init__(self, parent, raw_df: pd.DataFrame, file_path: str, on_confirm_callback, log_callback=None):
        super().__init__(parent)
        self.app = parent
        self.raw_df = raw_df.copy().reset_index(drop=True)
        self.file_path = file_path
        self.on_confirm_callback = on_confirm_callback
        self.log = log_callback or (lambda msg: None)

        self.title("Excel 数据清洗与列映射提取")
        self.configure(bg=THEME["bg"])
        self.transient(parent)
        self.grab_set()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        dlg_w = min(1860, max(1280, int(screen_w * 0.94)))
        dlg_h = min(1100, max(750, int(screen_h * 0.88)))

        self.minsize(1050, 650)
        self.resizable(True, True)

        pos_x = max(0, (screen_w - dlg_w) // 2)
        pos_y = max(0, (screen_h - dlg_h) // 2)
        self.geometry(f"{dlg_w}x{dlg_h}+{pos_x}+{pos_y}")

        self.selected_indices = set()
        self.all_selected = False

        self.mapping_vars = {}
        self.header_boxes = {}
        self.header_labels = {}
        self.header_combos = {}
        self.row_buttons = {}

        self.col_w_chk = 65
        self.col_w_seq = 55
        self.col_w_op = 90
        self.head_height = 68

        self.base_data_widths = {}
        self.cur_col_widths = {}
        self.last_container_width = 0

        self.inline_edit_entry = None

        self._calc_base_widths()
        self._setup_tree_styles()
        self._create_widgets()
        self._refresh_table()

    def _setup_tree_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Clean.Treeview", font=("Microsoft YaHei UI", 9), background="white", fieldbackground="white", foreground=THEME["text_main"], rowheight=34, bordercolor=THEME["border"], borderwidth=1)
        style.map("Clean.Treeview", background=[("selected", "#E0F2FE")], foreground=[("selected", "#0369A1")])

    def _calc_base_widths(self):
        for c_idx in range(len(self.raw_df.columns)):
            max_len = 0
            for val in self.raw_df[c_idx].dropna().head(40):
                s = str(val).strip()
                if s and s != "nan":
                    char_len = sum(2 if ord(c) > 127 else 1 for c in s)
                    if char_len > max_len:
                        max_len = char_len

            w = max(140, min(300, max_len * 7 + 38))
            self.base_data_widths[c_idx] = w
            self.cur_col_widths[c_idx] = w

    def _smart_infer_column(self, col_idx: int) -> str:
        samples = []
        for val in self.raw_df[col_idx].dropna().head(10):
            s = str(val).strip()
            if s and s != "nan":
                samples.append(s)

        if not samples:
            return "(不提取)"

        for s in samples:
            clean_digits = re.sub(r"\D", "", s)
            if len(clean_digits) >= 11 and (clean_digits.startswith("1") or clean_digits.startswith("861")):
                return "手机号"

        combined_text = " ".join(samples).lower()

        if any(k in combined_text for k in ["手机", "电话", "号码", "tel", "phone"]):
            return "手机号"
        if any(k in combined_text for k in ["姓名", "客户", "业主", "联系人", "名字", "name"]):
            return "姓名"
        if any(k in combined_text for k in ["小区", "项目", "社区", "花园", "苑", "楼盘"]):
            return "小区"
        if any(k in combined_text for k in ["栋", "幢", "座", "号楼"]):
            return "楼栋"
        if "单元" in combined_text:
            return "单元"
        if any(k in combined_text for k in ["房号", "室", "房", "户", "门牌"]):
            return "房号"

        return "(不提取)"

    def _create_widgets(self):
        top_bar = tk.Frame(self, bg=THEME["card_bg"], highlightbackground=THEME["border"], highlightthickness=1, padx=15, pady=10)
        top_bar.pack(fill=tk.X, padx=12, pady=(10, 5))

        tk.Label(top_bar, text="📁 数据源文件: ", font=("Microsoft YaHei UI", 9, "bold"), fg=THEME["text_main"], bg=THEME["card_bg"]).pack(side=tk.LEFT)
        tk.Label(top_bar, text=f"{self.file_path}", font=("Consolas", 9), fg="#2563EB", bg=THEME["card_bg"]).pack(side=tk.LEFT, padx=(0, 15))

        self.lbl_stats = tk.Label(top_bar, text=f"有效记录: {len(self.raw_df)} 行 | 已选: 0 项", font=("Microsoft YaHei UI", 9, "bold"), fg="#059669", bg=THEME["card_bg"])
        self.lbl_stats.pack(side=tk.LEFT, padx=10)

        tk.Label(top_bar, text="💡 提示: 双击单元格可修改；点击第1列勾选；点击操作列图标删除行", font=("Microsoft YaHei UI", 8), fg="#6B7280", bg=THEME["card_bg"]).pack(side=tk.LEFT, padx=15)

        ModernButton(
            top_bar,
            text="\U0001f5d1 删除勾选项",
            command=self.delete_selected_rows,
            bg="#EF4444",
            hover_bg="#DC2626",
            padx=10,
            pady=3,
            font=("Microsoft YaHei UI", 8, "bold")
        ).pack(side=tk.RIGHT, padx=5)

        table_card = tk.LabelFrame(
            self,
            text="  数据清洗列表（每列顶部下拉选择提取目标；双击编辑；支持横向平滑滚动与列宽自适应）  ",
            font=("Microsoft YaHei UI", 9, "bold"),
            bg=THEME["card_bg"],
            fg=THEME["text_main"],
            highlightbackground=THEME["border"],
            highlightthickness=1,
            padx=10,
            pady=8
        )
        table_card.pack(fill=tk.BOTH, expand=True, padx=12, pady=5)

        self.table_container = tk.Frame(table_card, bg=THEME["card_bg"])
        self.table_container.pack(fill=tk.BOTH, expand=True)

        self.head_canvas = tk.Canvas(self.table_container, bg="#F3F4F6", height=self.head_height + 2, highlightthickness=0)
        self.head_frame = tk.Frame(self.head_canvas, bg="#F3F4F6")
        self.head_canvas_window = self.head_canvas.create_window((0, 0), window=self.head_frame, anchor="nw")

        self.head_spacer = tk.Frame(self.table_container, bg="#E5E7EB", width=17, height=self.head_height + 2)

        self.tree_cols = ["勾选", "序号"] + [f"col_{i}" for i in range(len(self.raw_df.columns))] + ["操作"]
        self.tree = ttk.Treeview(self.table_container, columns=self.tree_cols, show="", selectmode="extended", style="Clean.Treeview")

        self.tree.column("勾选", width=self.col_w_chk, stretch=False, anchor="center")
        self.tree.column("序号", width=self.col_w_seq, stretch=False, anchor="center")
        for i in range(len(self.raw_df.columns)):
            self.tree.column(f"col_{i}", width=self.cur_col_widths[i], stretch=False, anchor="center")
        self.tree.column("操作", width=self.col_w_op, stretch=False, anchor="center")

        self._build_header_controls()

        v_scroll = ttk.Scrollbar(self.table_container, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(self.table_container, orient=tk.HORIZONTAL, command=self._on_horizontal_scroll)

        def sync_x_scroll(first, last):
            h_scroll.set(first, last)
            self.head_canvas.xview_moveto(first)
            self._update_button_positions()

        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=sync_x_scroll)

        self.head_canvas.grid(row=0, column=0, sticky="ew")
        self.head_spacer.grid(row=0, column=1, sticky="nsew")
        self.tree.grid(row=1, column=0, sticky="nsew")
        v_scroll.grid(row=1, column=1, sticky="ns")
        h_scroll.grid(row=2, column=0, sticky="ew")

        self.table_container.grid_rowconfigure(1, weight=1)
        self.table_container.grid_columnconfigure(0, weight=1)

        self.tree.bind("<ButtonRelease-1>", self._on_tree_cell_click)
        self.tree.bind("<Double-1>", self._on_double_click_cell)
        self.table_container.bind("<Configure>", self._on_container_configure)
        self.tree.bind("<Configure>", lambda e: self._update_button_positions())
        self.tree.bind("<MouseWheel>", lambda e: self.after(50, self._update_button_positions))

        bot_bar = tk.Frame(self, bg=THEME["card_bg"], padx=15, pady=12)
        bot_bar.pack(fill=tk.X, side="bottom")

        ModernButton(bot_bar, text="✔ 完成清洗并导入主页", command=self.on_import_clicked, bg=THEME["primary"], hover_bg=THEME["primary_hover"]).pack(side=tk.RIGHT, padx=5)
        ModernButton(bot_bar, text="取消", command=self.destroy, bg="#E5E7EB", hover_bg="#D1D5DB", fg="#374151").pack(side=tk.RIGHT, padx=5)

    def _on_tree_cell_click(self, event):
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
        self._update_stats_label()

    def toggle_select_all(self):
        if not self.all_selected:
            self.selected_indices = set(self.raw_df.index.tolist())
            self.all_selected = True
            self.lbl_select_all.config(text="[√] 全选")
        else:
            self.selected_indices.clear()
            self.all_selected = False
            self.lbl_select_all.config(text="[  ] 全选")

        self._refresh_table()

    def _update_stats_label(self):
        self.lbl_stats.config(text=f"有效记录: {len(self.raw_df)} 行 | 已选: {len(self.selected_indices)} 项")

    def _on_double_click_cell(self, event):
        if self.inline_edit_entry:
            self._save_inline_edit()

        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column_id = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id or column_id in ["#1", "#2", f"#{len(self.tree_cols)}"]:
            return

        col_num = int(column_id.replace("#", "")) - 3
        row_idx = int(row_id)

        bbox = self.tree.bbox(row_id, column=column_id)
        if not bbox:
            return
        x, y, w, h = bbox

        current_val = str(self.raw_df.at[row_idx, col_num]) if row_idx in self.raw_df.index else ""
        if current_val in ["nan", "-"]:
            current_val = ""

        entry = tk.Entry(self.tree, font=("Microsoft YaHei UI", 9), relief=tk.SOLID, bd=1)
        entry.insert(0, current_val)
        entry.select_range(0, tk.END)
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()

        self.inline_edit_entry = entry

        def finish_edit(save=True):
            if not self.inline_edit_entry:
                return
            if save:
                new_val = entry.get().strip()
                self.raw_df.at[row_idx, col_num] = new_val
                vals = list(self.tree.item(row_id, "values"))
                vals[col_num + 2] = new_val if new_val else "-"
                self.tree.item(row_id, values=vals)
            entry.destroy()
            self.inline_edit_entry = None

        entry.bind("<Return>", lambda e: finish_edit(True))
        entry.bind("<Escape>", lambda e: finish_edit(False))
        entry.bind("<FocusOut>", lambda e: finish_edit(True))

    def _save_inline_edit(self):
        if self.inline_edit_entry:
            try:
                self.inline_edit_entry.destroy()
            except Exception:
                pass
            self.inline_edit_entry = None

    def _build_header_controls(self):
        for child in self.head_frame.winfo_children():
            child.destroy()
        self.header_boxes.clear()
        self.header_labels.clear()
        self.header_combos.clear()

        chk_box = tk.Frame(self.head_frame, bg="#E5E7EB", width=self.col_w_chk, height=self.head_height, bd=0, highlightthickness=0)
        chk_box.pack_propagate(False)
        chk_box.pack(side=tk.LEFT, fill=tk.Y)
        self.lbl_select_all = tk.Label(
            chk_box,
            text="[√] 全选" if self.all_selected else "[  ] 全选",
            font=("Microsoft YaHei UI", 8, "bold"),
            fg="#2563EB",
            bg="#E5E7EB",
            cursor="hand2"
        )
        self.lbl_select_all.pack(expand=True)
        self.lbl_select_all.bind("<Button-1>", lambda e: self.toggle_select_all())

        seq_box = tk.Frame(self.head_frame, bg="#E5E7EB", width=self.col_w_seq, height=self.head_height, bd=0, highlightthickness=0)
        seq_box.pack_propagate(False)
        seq_box.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(seq_box, text="序号", font=("Microsoft YaHei UI", 9, "bold"), fg=THEME["text_main"], bg="#E5E7EB").pack(expand=True)

        options = ["(不提取)"] + FIXED_HEADERS

        for c_idx in range(len(self.raw_df.columns)):
            col_w = self.cur_col_widths[c_idx]
            col_box = tk.Frame(self.head_frame, bg="#F9FAFB", width=col_w, height=self.head_height, bd=0, highlightthickness=0)
            col_box.pack_propagate(False)
            col_box.pack(side=tk.LEFT, fill=tk.Y)
            self.header_boxes[c_idx] = col_box

            if c_idx not in self.mapping_vars:
                var = tk.StringVar(value=self._smart_infer_column(c_idx))
                self.mapping_vars[c_idx] = var
            else:
                var = self.mapping_vars[c_idx]

            lbl_title = tk.Label(col_box, text=f"第 {c_idx + 1} 列", font=("Microsoft YaHei UI", 8, "bold"), fg="#4B5563", bg="#F9FAFB")
            lbl_title.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(4, 2))
            self.header_labels[c_idx] = lbl_title

            cbo = ttk.Combobox(col_box, textvariable=var, values=options, state="readonly", font=("Microsoft YaHei UI", 9))
            cbo.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(2, 6))
            cbo.bind("<<ComboboxSelected>>", lambda e, idx=c_idx: self._update_header_style(idx))
            self.header_combos[c_idx] = cbo

            self._update_header_style(c_idx)

        op_box = tk.Frame(self.head_frame, bg="#E5E7EB", width=self.col_w_op, height=self.head_height, bd=0, highlightthickness=0)
        op_box.pack_propagate(False)
        op_box.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(op_box, text="操作", font=("Microsoft YaHei UI", 9, "bold"), fg=THEME["text_main"], bg="#E5E7EB").pack(expand=True)

        self.head_frame.update_idletasks()
        total_w = self.col_w_chk + self.col_w_seq + sum(self.cur_col_widths.values()) + self.col_w_op
        self.head_canvas.config(scrollregion=(0, 0, total_w, self.head_height))

    def _on_container_configure(self, event):
        avail_w = event.width - 24
        if avail_w <= 200 or abs(avail_w - self.last_container_width) < 6:
            return
        self.last_container_width = avail_w

        num_cols = len(self.raw_df.columns)
        if num_cols == 0:
            return

        base_total = self.col_w_chk + self.col_w_seq + sum(self.base_data_widths.values()) + self.col_w_op

        if avail_w > base_total:
            extra = avail_w - base_total
            add_per_col = extra // num_cols
            remainder = extra % num_cols
            for c_idx in range(num_cols):
                extra_pixel = add_per_col + (1 if c_idx < remainder else 0)
                self.cur_col_widths[c_idx] = self.base_data_widths[c_idx] + extra_pixel
        else:
            for c_idx in range(num_cols):
                self.cur_col_widths[c_idx] = self.base_data_widths[c_idx]

        for c_idx in range(num_cols):
            w = self.cur_col_widths[c_idx]
            self.tree.column(f"col_{c_idx}", width=w)
            if c_idx in self.header_boxes:
                self.header_boxes[c_idx].config(width=w)

        self.head_frame.update_idletasks()
        total_w = self.col_w_chk + self.col_w_seq + sum(self.cur_col_widths.values()) + self.col_w_op
        self.head_canvas.config(scrollregion=(0, 0, total_w, self.head_height))
        self._update_button_positions()

    def _update_header_style(self, c_idx: int):
        var = self.mapping_vars.get(c_idx)
        box = self.header_boxes.get(c_idx)
        lbl = self.header_labels.get(c_idx)
        if not (var and box and lbl):
            return

        val = var.get()
        if val != "(不提取)":
            box.config(bg="#E0F2FE")
            lbl.config(bg="#E0F2FE", fg="#0369A1", text=f"第 {c_idx + 1} 列 ➜ [{val}]")
        else:
            box.config(bg="#F9FAFB")
            lbl.config(bg="#F9FAFB", fg="#6B7280", text=f"第 {c_idx + 1} 列 (不提取)")

    def _on_horizontal_scroll(self, *args):
        self._save_inline_edit()
        self.tree.xview(*args)
        self.head_canvas.xview(*args)
        self._update_button_positions()

    def _refresh_table(self):
        self._save_inline_edit()
        for btn in self.row_buttons.values():
            btn.destroy()
        self.row_buttons.clear()

        for item in self.tree.get_children():
            self.tree.delete(item)

        self._update_stats_label()

        for idx, row in self.raw_df.iterrows():
            chk_char = "[√]" if idx in self.selected_indices else "[  ]"
            vals = [chk_char, idx + 1]

            for c_idx in range(len(self.raw_df.columns)):
                raw_v = row[c_idx]
                v = str(raw_v).strip() if pd.notna(raw_v) and str(raw_v).strip() != "nan" else "-"
                vals.append(v)
            vals.append("")

            self.tree.insert("", tk.END, iid=idx, values=vals)

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
            self.row_buttons[idx] = btn_del

        self.after(100, self._update_button_positions)

    def _update_button_positions(self):
        for idx, btn in self.row_buttons.items():
            bbox = self.tree.bbox(idx, column="操作")
            if bbox and len(bbox) == 4:
                x, y, w, h = bbox
                btn_size = 24
                if w < btn_size + 4:
                    btn.place_forget()
                    continue
                btn_x = x + (w - btn_size) // 2
                btn_y = y + (h - btn_size) // 2
                btn.place(x=btn_x, y=btn_y, width=btn_size, height=btn_size)
            else:
                btn.place_forget()

    def delete_row(self, idx: int):
        self._save_inline_edit()
        self.raw_df = self.raw_df.drop(index=idx).reset_index(drop=True)
        new_selected = set()
        for s_idx in self.selected_indices:
            if s_idx < idx:
                new_selected.add(s_idx)
            elif s_idx > idx:
                new_selected.add(s_idx - 1)
        self.selected_indices = new_selected
        self._refresh_table()

    def delete_selected_rows(self):
        self._save_inline_edit()
        tree_sel = [int(iid) for iid in self.tree.selection()]
        target_indices = sorted(list(self.selected_indices.union(tree_sel)))

        if not target_indices:
            messagebox.showinfo("提示", "请先通过第 1 列勾选或选中需要删除的数据行！")
            return

        if messagebox.askyesno("确认删除", f"确定要删除已勾选/选中的 {len(target_indices)} 行数据吗？"):
            self.raw_df = self.raw_df.drop(index=target_indices).reset_index(drop=True)
            self.selected_indices.clear()
            self.all_selected = False
            self.lbl_select_all.config(text="[  ] 全选")
            self._refresh_table()

    def on_import_clicked(self):
        self._save_inline_edit()
        if self.raw_df.empty:
            messagebox.showwarning("警告", "当前无有效数据可导入！")
            return

        mapped_headers = {}
        for c_idx, var in self.mapping_vars.items():
            target = var.get()
            if target != "(不提取)":
                if target in mapped_headers:
                    messagebox.showerror(
                        "冲突",
                        f"目标项【{target}】被重复指定在【第 {mapped_headers[target] + 1} 列】和【第 {c_idx + 1} 列】！\n每个目标项只能由一列提取。"
                    )
                    return
                mapped_headers[target] = c_idx

        missing_headers = [h for h in FIXED_HEADERS if h not in mapped_headers]

        if missing_headers:
            MissingHeadersInputDialog(
                self,
                missing_headers,
                on_confirm_callback=lambda defaults: self._generate_and_import(mapped_headers, defaults)
            )
        else:
            self._generate_and_import(mapped_headers, defaults={})

    def _generate_and_import(self, mapped_headers: dict, defaults: dict):
        clean_data = []

        for _, row in self.raw_df.iterrows():
            item = {}
            for h in FIXED_HEADERS:
                if h in mapped_headers:
                    c_idx = mapped_headers[h]
                    raw_val = row[c_idx]
                    val_str = str(raw_val).strip() if pd.notna(raw_val) and str(raw_val).strip() not in ["nan", "-"] else ""
                    if h == FIXED_PHONE_COL:
                        val_str = clean_phone_number(val_str)
                    elif h in ["楼栋", "单元"]:
                        val_str = format_building_and_unit(h, val_str)
                    item[h] = val_str
                else:
                    default_v = defaults.get(h, "")
                    if h == FIXED_PHONE_COL:
                        default_v = clean_phone_number(default_v)
                    elif h in ["楼栋", "单元"]:
                        default_v = format_building_and_unit(h, default_v)
                    item[h] = default_v
            clean_data.append(item)

        final_df = pd.DataFrame(clean_data, columns=FIXED_HEADERS)

        before_count = len(final_df)
        final_df = final_df[final_df[FIXED_PHONE_COL].str.len() == 11].reset_index(drop=True)
        filtered_count = before_count - len(final_df)

        if final_df.empty:
            messagebox.showerror("错误", "提取到的数据中未发现有效的 11 位手机号，无法导入！")
            return

        if filtered_count > 0:
            self.log(f"🧹 手机号清洗：自动剔除号码不合规（非11位纯数字）的脏数据 {filtered_count} 条。")

        self.destroy()
        if self.on_confirm_callback:
            self.on_confirm_callback(final_df)
