import tkinter as tk
from tkinter import ttk, font as tkfont
import pandas as pd
from config import FIXED_HEADERS, FIXED_PHONE_COL
from ui_components import ModernButton

class ContactTableView(tk.Frame):
    """自适应高性能联系人数据表格组件"""

    def __init__(self, parent, on_single_add, on_delete_row, on_selection_changed):
        super().__init__(parent, bg="white")
        self.on_single_add = on_single_add
        self.on_delete_row = on_delete_row
        self.on_selection_changed = on_selection_changed

        self.df = None
        self.selected_indices = set()
        self.row_buttons = {}
        self.search_keyword = ""

        self.measure_font = tkfont.Font(family="Microsoft YaHei UI", size=9)
        self.header_font = tkfont.Font(family="Microsoft YaHei UI", size=9, weight="bold")

        self.col_base_widths = {}
        self.col_cur_widths = {}
        self.last_container_w = 0

        self.col_w_chk = 88
        self.col_w_seq = 60
        self.col_w_op = 105

        self._build_treeview()

    def _build_treeview(self):
        self.tree_cols = ["勾选", "序号"] + FIXED_HEADERS + ["微信备注", "状态", "操作"]
        self.tree = ttk.Treeview(self, columns=self.tree_cols, show="headings")

        self.tree.heading("勾选", text="[  ] 全选", command=self.toggle_select_all)
        self.tree.column("勾选", width=self.col_w_chk, stretch=False, anchor="center")

        self.tree.heading("序号", text="序号")
        self.tree.column("序号", width=self.col_w_seq, stretch=False, anchor="center")

        for h in FIXED_HEADERS + ["微信备注", "状态"]:
            self.col_base_widths[h] = 110
            self.col_cur_widths[h] = 110
            self.tree.heading(h, text=h)
            self.tree.column(h, width=110, stretch=False, anchor="center")

        self.tree.heading("操作", text="操作")
        self.tree.column("操作", width=self.col_w_op, stretch=False, anchor="center")

        v_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self._on_horizontal_scroll)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tree.bind("<ButtonRelease-1>", self._on_cell_click)
        self.bind("<Configure>", self.on_resize)
        self.tree.bind("<Configure>", lambda e: self.update_button_positions())
        self.tree.bind("<MouseWheel>", lambda e: self.after(50, self.update_button_positions))

    def set_data(self, df: pd.DataFrame):
        self.df = df
        self.selected_indices.clear()
        self.calc_optimal_widths()
        self.refresh()

    def set_search_keyword(self, kw: str):
        self.search_keyword = kw.strip()
        self.refresh()

    def get_visible_indices(self) -> list:
        if self.df is None or self.df.empty:
            return []
        if not self.search_keyword:
            return self.df.index.tolist()
        matched = []
        for idx, row in self.df.iterrows():
            if self.search_keyword in str(row.get(FIXED_PHONE_COL, "")).strip():
                matched.append(idx)
        return matched

    def calc_optimal_widths(self):
        if self.df is None or self.df.empty:
            return
        cols = FIXED_HEADERS + ["微信备注", "状态"]
        for col in cols:
            max_px = self.header_font.measure(str(col)) + 30
            if col in self.df.columns:
                for val in self.df[col].dropna().head(200):
                    s = str(val).strip()
                    if s and s not in ["nan", "-"]:
                        w_px = self.measure_font.measure(s) + 26
                        if w_px > max_px:
                            max_px = w_px

            if col == "手机号":
                w = max(125, max_px)
            elif col == "微信备注":
                w = max(220, min(550, max_px))
            elif col == "状态":
                w = max(135, min(300, max_px))
            elif col == "小区":
                w = max(130, min(350, max_px))
            else:
                w = max(85, min(220, max_px))

            self.col_base_widths[col] = w
            self.col_cur_widths[col] = w

    def on_resize(self, event=None):
        cur_w = event.width if (event and hasattr(event, "width")) else self.winfo_width()
        avail_w = cur_w - 24
        if avail_w <= 200 or abs(avail_w - self.last_container_w) < 6:
            return
        self.last_container_w = avail_w

        cols = FIXED_HEADERS + ["微信备注", "状态"]
        base_total = self.col_w_chk + self.col_w_seq + sum(self.col_base_widths.get(c, 110) for c in cols) + self.col_w_op

        if avail_w > base_total:
            extra = avail_w - base_total
            num_cols = len(cols)
            add_per_col = extra // num_cols
            rem = extra % num_cols
            for idx, c in enumerate(cols):
                self.col_cur_widths[c] = self.col_base_widths[c] + add_per_col + (1 if idx < rem else 0)
        else:
            for c in cols:
                self.col_cur_widths[c] = self.col_base_widths[c]

        for c in cols:
            self.tree.column(c, width=self.col_cur_widths[c])
        self.update_button_positions()

    def refresh(self):
        for btns in self.row_buttons.values():
            for b in btns:
                b.destroy()
        self.row_buttons.clear()

        for item in self.tree.get_children():
            self.tree.delete(item)

        if self.df is None or self.df.empty:
            self.on_selection_changed(0, 0, len(self.selected_indices))
            return

        visible = self.get_visible_indices()
        all_checked = visible and set(visible).issubset(self.selected_indices)
        self.tree.heading("勾选", text="[√] 全选" if all_checked else "[  ] 全选")

        for c in FIXED_HEADERS + ["微信备注", "状态"]:
            self.tree.column(c, width=self.col_cur_widths.get(c, 110))

        for idx in visible:
            row = self.df.loc[idx]
            chk = "[√]" if idx in self.selected_indices else "[  ]"
            row_vals = [chk, idx + 1] + [str(row[h]).strip() if pd.notna(row[h]) else "-" for h in FIXED_HEADERS]
            row_vals.extend([str(row.get("微信备注", "-")), str(row.get("状态", "未添加")), ""])

            self.tree.insert("", tk.END, iid=idx, values=row_vals)

            btn_add = ModernButton(self.tree, text="➕", command=lambda i=idx: self.on_single_add(i), padx=0, pady=0, font=("Segoe UI Symbol", 10, "bold"))
            btn_del = ModernButton(self.tree, text="\U0001f5d1", bg="#EF4444", hover_bg="#DC2626", command=lambda i=idx: self.on_delete_row(i), padx=0, pady=0, font=("Segoe UI Emoji", 10))
            self.row_buttons[idx] = (btn_add, btn_del)

        self.on_selection_changed(len(visible), len(self.df), len(self.selected_indices))
        self.after(100, self.update_button_positions)

    def update_button_positions(self):
        if self.df is None or self.df.empty:
            return
        for idx, btns in self.row_buttons.items():
            btn_add, btn_del = btns
            bbox = self.tree.bbox(idx, column="操作")
            if bbox and len(bbox) == 4:
                x, y, w, h = bbox
                size, margin = 24, 14
                total_w = size * 2 + margin
                start_x = x + max(4, (w - total_w) // 2)
                btn_y = y + max(1, (h - size) // 2)
                btn_add.place(x=start_x, y=btn_y, width=size, height=size)
                btn_del.place(x=start_x + size + margin, y=btn_y, width=size, height=size)
            else:
                btn_add.place_forget()
                btn_del.place_forget()

    def update_row_status(self, idx: int, remark: str, result: str):
        if self.tree.exists(idx):
            vals = list(self.tree.item(idx, "values"))
            vals[-3] = remark
            vals[-2] = result
            self.tree.item(idx, values=vals)
        if idx in self.row_buttons:
            btn_add, _ = self.row_buttons[idx]
            is_done = any(k in result for k in ["成功", "已是好友", "已发送"])
            btn_add.set_state("normal", text="✓" if is_done else "➕")
        self.update_button_positions()

    def toggle_select_all(self):
        """原地批量更新勾选态，杜绝组件销毁与全量重绘"""
        visible = self.get_visible_indices()
        if not visible:
            return

        v_set = set(visible)
        # 1. 计算目标勾选态
        if v_set.issubset(self.selected_indices):
            self.selected_indices.difference_update(v_set)
            is_checked = False
            chk_char = "[  ]"
            header_text = "[  ] 全选"
        else:
            self.selected_indices.update(v_set)
            is_checked = True
            chk_char = "[√]"
            header_text = "[√] 全选"

        # 2. 原地更新表头
        self.tree.heading("勾选", text=header_text)

        # 3. 仅就地批量修改已有项的第 1 列文本，不销毁/不重绘任何按钮
        for iid in visible:
            if self.tree.exists(iid):
                vals = list(self.tree.item(iid, "values"))
                vals[0] = chk_char
                self.tree.item(iid, values=vals)

        # 4. 仅触发统计数据回调
        self.on_selection_changed(len(visible), len(self.df), len(self.selected_indices))

    def _on_cell_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell" or self.tree.identify_column(event.x) != "#1":
            return
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        idx = int(row_id)
        if idx in self.selected_indices:
            self.selected_indices.remove(idx)
        else:
            self.selected_indices.add(idx)

        vals = list(self.tree.item(row_id, "values"))
        vals[0] = "[√]" if idx in self.selected_indices else "[  ]"
        self.tree.item(row_id, values=vals)
        self.on_selection_changed(len(self.get_visible_indices()), len(self.df), len(self.selected_indices))

    def _on_horizontal_scroll(self, *args):
        self.tree.xview(*args)
        self.update_button_positions()
