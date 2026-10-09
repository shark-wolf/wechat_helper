import tkinter as tk
from tkinter import ttk, messagebox
from config import THEME, GREETING_POOL, load_template_config, save_template_config
from ui_components import ModernButton, parse_placeholders

class TemplateConfigDialog(tk.Toplevel):
    def __init__(self, parent, on_save_callback=None, log_callback=None):
        super().__init__(parent)
        self.app = parent
        self.on_save_callback = on_save_callback
        self.log = log_callback or (lambda msg: None)

        self.title("自定义 Excel 模板、映射与去重规则")
        dlg_w, dlg_h = 950, 1100
        self.minsize(dlg_w, dlg_h)
        self.resizable(True, True)
        self.configure(bg=THEME["card_bg"])
        self.transient(parent)

        root_x, root_y = parent.winfo_x(), parent.winfo_y()
        root_w, root_h = parent.winfo_width(), parent.winfo_height()
        pos_x = root_x + max(0, (root_w - dlg_w) // 2)
        pos_y = root_y + max(0, (root_h - dlg_h) // 2)
        self.geometry(f"{dlg_w}x{dlg_h}+{pos_x}+{pos_y}")

        self.cfg = load_template_config()
        self._create_widgets()

    def _create_widgets(self):
        canvas = tk.Canvas(self, bg=THEME["card_bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=THEME["card_bg"])

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(canvas_window, width=e.width))

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="top", fill="both", expand=True, padx=15, pady=(15, 5))
        scrollbar.pack(side="right", fill="y")

        # ==================== 1. 定义表头列名 ====================
        sec1 = tk.LabelFrame(scrollable_frame, text=" 1. 定义 Excel 表头列名 ", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"], padx=12, pady=8)
        sec1.pack(fill=tk.X, pady=6)

        tk.Label(sec1, text="用逗号分隔各个列名：", font=("Microsoft YaHei UI", 9), bg=THEME["card_bg"], fg=THEME["text_sub"]).pack(anchor="w")

        ent_headers = tk.Entry(sec1, font=("Consolas", 10), relief=tk.SOLID, bd=1)
        ent_headers.pack(fill=tk.X, pady=(4, 4), ipady=3)
        ent_headers.insert(0, ", ".join(self.cfg.get("headers", ["手机号", "姓名", "小区", "楼栋", "单元", "房号"])))

        # 表头预览
        hdr_preview_frame = tk.Frame(sec1, bg="#F3F4F6", relief=tk.SOLID, bd=1, padx=6, pady=4)
        hdr_preview_frame.pack(fill=tk.X, pady=(2, 4))

        # ==================== 2. 映射与规则设置 ====================
        sec2 = tk.LabelFrame(scrollable_frame, text=" 2. 字段映射与招呼语/备注规则 ", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"], padx=12, pady=8)
        sec2.pack(fill=tk.X, pady=6)

        # ① 手机号列
        phone_f = tk.Frame(sec2, bg=THEME["card_bg"])
        phone_f.pack(fill=tk.X, pady=4)
        tk.Label(phone_f, text="① 目标手机号列 (必选):", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"]).pack(side=tk.LEFT)
        cbo_phone = ttk.Combobox(phone_f, state="readonly", width=20)
        cbo_phone.pack(side=tk.LEFT, padx=10)

        # ② 打招呼模式设置
        greet_sec = tk.Frame(sec2, bg=THEME["card_bg"])
        greet_sec.pack(fill=tk.X, pady=(8, 4))
        tk.Label(greet_sec, text="② 申请打招呼语发送模式:", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"]).pack(anchor="w")

        greet_mode_var = tk.StringVar(value=self.cfg.get("greeting_type", "manual"))

        # 模式1: 手动/模板输入
        rb_greet_manual = tk.Radiobutton(greet_sec, text="1- 手动输入/占位符招呼语（空值则使用系统默认）", variable=greet_mode_var, value="manual", bg=THEME["card_bg"], font=("Microsoft YaHei UI", 9))
        rb_greet_manual.pack(anchor="w", padx=10, pady=2)

        greet_input_f = tk.Frame(greet_sec, bg=THEME["card_bg"])
        greet_input_f.pack(fill=tk.X, padx=28, pady=2)
        ent_greeting = tk.Entry(greet_input_f, font=("Microsoft YaHei UI", 9), relief=tk.SOLID, bd=1)
        ent_greeting.pack(fill=tk.X, ipady=2)
        ent_greeting.insert(0, self.cfg.get("greeting_template", "你好，简单沟通一下！"))

        # 模式2: 随机语池（可编辑与列出）
        rb_greet_def = tk.Radiobutton(greet_sec, text="2- 直接选择系统默认随机语池（下方可自定义编辑语料池，每行一条）：", variable=greet_mode_var, value="default", bg=THEME["card_bg"], font=("Microsoft YaHei UI", 9))
        rb_greet_def.pack(anchor="w", padx=10, pady=(6, 2))

        # 语池编辑器容器
        pool_container = tk.Frame(greet_sec, bg="#F9FAFB", relief=tk.SOLID, bd=1, padx=8, pady=6)
        pool_container.pack(fill=tk.X, padx=28, pady=(2, 6))

        pool_top_bar = tk.Frame(pool_container, bg="#F9FAFB")
        pool_top_bar.pack(fill=tk.X, pady=(0, 4))
        lbl_pool_stats = tk.Label(pool_top_bar, text="📋 随机语池列表（每行一条）:", font=("Microsoft YaHei UI", 8, "bold"), fg="#374151", bg="#F9FAFB")
        lbl_pool_stats.pack(side=tk.LEFT)

        btn_reset_pool = tk.Label(pool_top_bar, text="[恢复初始预设]", font=("Microsoft YaHei UI", 8), fg="#2563EB", bg="#F9FAFB", cursor="hand2")
        btn_reset_pool.pack(side=tk.RIGHT)

        txt_pool = tk.Text(pool_container, height=6, wrap=tk.WORD, font=("Microsoft YaHei UI", 9), relief=tk.SOLID, bd=1)
        txt_pool_scroll = ttk.Scrollbar(pool_container, orient=tk.VERTICAL, command=txt_pool.yview)
        txt_pool.configure(yscrollcommand=txt_pool_scroll.set)
        txt_pool.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        txt_pool_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 加载语料数据
        saved_greetings = self.cfg.get("greetings", GREETING_POOL)
        if not saved_greetings:
            saved_greetings = GREETING_POOL
        txt_pool.insert("1.0", "\n".join(saved_greetings))

        def reset_to_default_pool(e=None):
            if messagebox.askyesno("重置确认", "确定将语池恢复为系统预设语料吗？"):
                txt_pool.delete("1.0", tk.END)
                txt_pool.insert("1.0", "\n".join(GREETING_POOL))
                update_previews()

        btn_reset_pool.bind("<Button-1>", reset_to_default_pool)

        # 打招呼语预览盒子
        prev_greet_box = tk.Frame(greet_sec, bg="#EFF6FF", relief=tk.SOLID, bd=1, padx=8, pady=5)
        prev_greet_box.pack(fill=tk.X, padx=10, pady=(4, 6))
        lbl_prev_greet = tk.Label(prev_greet_box, text="✨ 打招呼语拼接预览: -", font=("Microsoft YaHei UI", 8), fg="#1E40AF", bg="#EFF6FF", anchor="w")
        lbl_prev_greet.pack(fill=tk.X)

        def on_greet_mode_toggle():
            is_manual = (greet_mode_var.get() == "manual")
            if is_manual:
                ent_greeting.config(state="normal", bg="white")
                txt_pool.config(state="disabled", bg="#E5E7EB", fg="#6B7280")
            else:
                ent_greeting.config(state="disabled", bg="#E5E7EB")
                txt_pool.config(state="normal", bg="white", fg=THEME["text_main"])
            update_previews()

        rb_greet_manual.config(command=on_greet_mode_toggle)
        rb_greet_def.config(command=on_greet_mode_toggle)

        # ③ 微信备注占位符组合
        remark_sec = tk.Frame(sec2, bg=THEME["card_bg"])
        remark_sec.pack(fill=tk.X, pady=(10, 4))

        rem_head_f = tk.Frame(remark_sec, bg=THEME["card_bg"])
        rem_head_f.pack(fill=tk.X)
        tk.Label(rem_head_f, text="③ 微信备注组合配置:", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"]).pack(side=tk.LEFT)
        tk.Label(rem_head_f, text="（示例：${姓名}-${手机号}）", font=("Microsoft YaHei UI", 8), fg="#6B7280", bg=THEME["card_bg"]).pack(side=tk.LEFT, padx=5)

        ent_remark = tk.Entry(remark_sec, font=("Consolas", 10), relief=tk.SOLID, bd=1)
        ent_remark.pack(fill=tk.X, pady=4, ipady=3)
        ent_remark.insert(0, self.cfg.get("remark_template", "${小区}${楼栋}${单元}${房号}-${姓名}(${手机号})"))

        tags_f = tk.Frame(remark_sec, bg=THEME["card_bg"])
        tags_f.pack(fill=tk.X, pady=2)
        tk.Label(tags_f, text="点击标签快捷插入占位符:", font=("Microsoft YaHei UI", 8), fg="#4B5563", bg=THEME["card_bg"]).pack(side=tk.LEFT)
        tags_container = tk.Frame(tags_f, bg=THEME["card_bg"])
        tags_container.pack(side=tk.LEFT, padx=5)

        prev_remark_box = tk.Frame(remark_sec, bg="#ECFDF5", relief=tk.SOLID, bd=1, padx=8, pady=5)
        prev_remark_box.pack(fill=tk.X, pady=(6, 4))
        lbl_prev_remark = tk.Label(prev_remark_box, text="✨ 微信备注组合拼接预览: -", font=("Microsoft YaHei UI", 8, "bold"), fg="#047857", bg="#ECFDF5", anchor="w")
        lbl_prev_remark.pack(fill=tk.X)

        # ==================== 3. 去重规则设置 ====================
        sec3 = tk.LabelFrame(scrollable_frame, text=" 3. Excel 导入去重数据组合 ", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"], padx=12, pady=8)
        sec3.pack(fill=tk.X, pady=6)

        tk.Label(sec3, text="勾选组合构成唯一性 Key（导入 Excel 时将自动依此去重）：", font=("Microsoft YaHei UI", 8), fg="#4B5563", bg=THEME["card_bg"]).pack(anchor="w")

        dedup_chk_f = tk.Frame(sec3, bg="#F9FAFB", relief=tk.SOLID, bd=1, padx=8, pady=4)
        dedup_chk_f.pack(fill=tk.X, pady=4)
        dedup_vars = {}

        def insert_tag(tag_str):
            ent_remark.insert(tk.INSERT, tag_str)
            update_previews()

        def update_previews(*args):
            raw = ent_headers.get().replace("，", ",").strip()
            cols = [c.strip() for c in raw.split(",") if c.strip()]

            # 1. 刷新模拟表头 Badge 预览
            for child in hdr_preview_frame.winfo_children():
                child.destroy()

            if not cols:
                tk.Label(hdr_preview_frame, text="(等待输入表头列名)", font=("Microsoft YaHei UI", 8), fg="#9CA3AF", bg="#F3F4F6").pack()
            else:
                for col_name in cols:
                    lbl = tk.Label(hdr_preview_frame, text=f" {col_name} ", font=("Microsoft YaHei UI", 8, "bold"), bg="#3B82F6", fg="white", padx=5, pady=1)
                    lbl.pack(side=tk.LEFT, padx=3, pady=2)

            # 2. 刷新手机号下拉框选项
            cbo_phone["values"] = cols
            if cbo_phone.get() not in cols and cols:
                cbo_phone.set(cols[0])

            # 3. 刷新快捷标签
            for child in tags_container.winfo_children():
                child.destroy()
            for col_name in cols:
                tag_btn = tk.Label(tags_container, text=f"+${{{col_name}}}", font=("Consolas", 8), bg="#E0F2FE", fg="#0369A1", cursor="hand2", padx=4, pady=1, relief=tk.SOLID, bd=1)
                tag_btn.pack(side=tk.LEFT, padx=2)
                tag_btn.bind("<Button-1>", lambda e, t=f"${{{col_name}}}": insert_tag(t))

            # 4. 刷新去重勾选框列表
            cur_checked = [c for c, v in dedup_vars.items() if v.get()]
            if not dedup_vars:
                saved_dedup = self.cfg.get("dedup_cols", ["手机号"])
                cur_checked = [c for c in saved_dedup if c in cols]

            for child in dedup_chk_f.winfo_children():
                child.destroy()
            dedup_vars.clear()

            for col_name in cols:
                var = tk.BooleanVar(value=(col_name in cur_checked or col_name == cbo_phone.get()))
                dedup_vars[col_name] = var
                cb = tk.Checkbutton(dedup_chk_f, text=col_name, variable=var, bg="#F9FAFB", activebackground="#F9FAFB", font=("Microsoft YaHei UI", 9))
                cb.pack(side=tk.LEFT, padx=6, pady=2)

            # 5. 自动带入模拟示例数据进行实时预览
            mock_data = {}
            for c in cols:
                if c == cbo_phone.get():
                    mock_data[c] = "15888888888"
                elif "名" in c or "客户" in c or "人" in c:
                    mock_data[c] = "李二"
                elif "址" in c or "房" in c or "区" in c or "地址" in c:
                    mock_data[c] = "中海右岸1栋1单元801"
                elif "司" in c or "公司" in c or "机构" in c:
                    mock_data[c] = "极客科技"
                else:
                    mock_data[c] = f"示例{c}"

            # 打招呼预览更新
            if greet_mode_var.get() == "default":
                # 解析语池有效条数
                pool_lines = [l.strip() for l in txt_pool.get("1.0", tk.END).split("\n") if l.strip()]
                sample_item = pool_lines[0] if pool_lines else "你好！"
                lbl_pool_stats.config(text=f"📋 随机语池列表（共 {len(pool_lines)} 条，每行一条）:")
                lbl_prev_greet.config(text=f"✨ 打招呼语拼接预览: 【系统随机抽取，如: \"{sample_item}\" (共{len(pool_lines)}条备选)】")
            else:
                g_tpl = ent_greeting.get().strip()
                parsed_g = parse_placeholders(g_tpl, mock_data)
                if not parsed_g:
                    lbl_prev_greet.config(text="✨ 打招呼语拼接预览: (输入留空，运行时自动使用系统默认)")
                else:
                    lbl_prev_greet.config(text=f"✨ 打招呼语拼接预览: 【 {parsed_g} 】")

            # 微信备注预览更新
            r_tpl = ent_remark.get().strip()
            parsed_r = parse_placeholders(r_tpl, mock_data)
            if not parsed_r:
                lbl_prev_remark.config(text="✨ 微信备注组合拼接预览: (未设置组合或为空)")
            else:
                lbl_prev_remark.config(text=f"✨ 微信备注组合拼接预览: 【 {parsed_r} 】")

        ent_headers.bind("<KeyRelease>", update_previews)
        ent_greeting.bind("<KeyRelease>", update_previews)
        txt_pool.bind("<KeyRelease>", update_previews)
        ent_remark.bind("<KeyRelease>", update_previews)

        update_previews()

        if self.cfg.get("phone_col") in cbo_phone["values"]:
            cbo_phone.set(self.cfg["phone_col"])
        on_greet_mode_toggle()

        def on_save():
            raw = ent_headers.get().replace("，", ",").strip()
            cols = [c.strip() for c in raw.split(",") if c.strip()]
            if not cols:
                messagebox.showerror("错误", "表头列名不能为空！")
                return

            p_col = cbo_phone.get().strip()
            if not p_col or p_col not in cols:
                messagebox.showerror("错误", "必须选择有效的【目标手机号列】！")
                return

            g_mode = greet_mode_var.get()
            g_tpl = ent_greeting.get().strip()
            r_tpl = ent_remark.get().strip()
            d_cols = [c for c, v in dedup_vars.items() if v.get()]

            # 读取编辑后的语池数据
            pool_content = txt_pool.get("1.0", tk.END).strip()
            pool_lines = [line.strip() for line in pool_content.split("\n") if line.strip()]
            if not pool_lines:
                pool_lines = GREETING_POOL.copy()

            new_cfg = {
                "headers": cols,
                "phone_col": p_col,
                "greeting_type": g_mode,
                "greeting_template": g_tpl,
                "greetings": pool_lines,
                "remark_template": r_tpl,
                "dedup_cols": d_cols
            }
            save_template_config(new_cfg)
            if self.on_save_callback:
                self.on_save_callback(new_cfg)

            self.log(f"⚙️ 配置已更存: 手机号=[{p_col}], 招呼模式=[{g_mode}], 语池容量=[{len(pool_lines)}条], 备注模板=[{r_tpl}], 去重组合=[{'+'.join(d_cols)}]")
            messagebox.showinfo("成功", "模板及规则配置已生效并保存！")
            self.destroy()

        btn_row = tk.Frame(self, bg=THEME["card_bg"], padx=5, pady=5)
        btn_row.pack(fill=tk.X, side="bottom", padx=20, pady=10)
        ModernButton(btn_row, text="保存配置", command=on_save, bg=THEME["primary"], hover_bg=THEME["primary_hover"]).pack(side=tk.RIGHT, padx=5)
        ModernButton(btn_row, text="取消", command=self.destroy, bg="#E5E7EB", hover_bg="#D1D5DB", fg="#374151").pack(side=tk.RIGHT, padx=5)
