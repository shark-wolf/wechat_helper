import tkinter as tk
from tkinter import messagebox
from config import THEME, load_safety_config, save_safety_config
from ui_components import ModernButton

class SafetyConfigDialog(tk.Toplevel):
    def __init__(self, parent, on_save_callback=None, log_callback=None):
        super().__init__(parent)
        self.app = parent
        self.on_save_callback = on_save_callback
        self.log = log_callback or (lambda msg: None)

        self.title("安全风控与拟人参数设置")
        dlg_w, dlg_h = 620, 480
        self.resizable(False, False)
        self.configure(bg=THEME["card_bg"])
        self.transient(parent)

        root_x, root_y = parent.winfo_x(), parent.winfo_y()
        root_w, root_h = parent.winfo_width(), parent.winfo_height()
        pos_x = root_x + max(0, (root_w - dlg_w) // 2)
        pos_y = root_y + max(0, (root_h - dlg_h) // 2)
        self.geometry(f"{dlg_w}x{dlg_h}+{pos_x}+{pos_y}")

        self.cfg = load_safety_config()
        self._create_widgets()

    def _create_widgets(self):
        # 头部说明
        header_f = tk.Frame(self, bg=THEME["card_bg"], padx=20, pady=12)
        header_f.pack(fill=tk.X)
        tk.Label(header_f, text="🛡️ 拟人化行为与防风控参数配置", font=("Microsoft YaHei UI", 11, "bold"), fg=THEME["text_main"], bg=THEME["card_bg"]).pack(anchor="w")
        tk.Label(header_f, text="合理设置添加间隔可极大降低微信限制与频繁报错的风险。", font=("Microsoft YaHei UI", 8), fg=THEME["text_sub"], bg=THEME["card_bg"]).pack(anchor="w", pady=(2, 0))

        content_f = tk.Frame(self, bg=THEME["card_bg"], padx=20)
        content_f.pack(fill=tk.BOTH, expand=True)

        # 1. 单日添加上限
        box1 = tk.LabelFrame(content_f, text=" 单日总量保护 ", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"], padx=15, pady=10)
        box1.pack(fill=tk.X, pady=6)

        row1 = tk.Frame(box1, bg=THEME["card_bg"])
        row1.pack(fill=tk.X)
        tk.Label(row1, text="单日添加上限 (人):", font=("Microsoft YaHei UI", 9), bg=THEME["card_bg"]).pack(side=tk.LEFT)
        self.ent_daily_max = tk.Entry(row1, font=("Consolas", 10), width=10, relief=tk.SOLID, bd=1)
        self.ent_daily_max.pack(side=tk.LEFT, padx=10)
        self.ent_daily_max.insert(0, str(self.cfg.get("DAILY_MAX_LIMIT", 100)))
        tk.Label(row1, text="(达到上限后将自动停止批量添加)", font=("Microsoft YaHei UI", 8), fg=THEME["text_sub"], bg=THEME["card_bg"]).pack(side=tk.LEFT)

        # 2. 批量单次操作冷却时间
        box2 = tk.LabelFrame(content_f, text=" 批量每次添加后的冷却时间 (秒) ", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"], padx=15, pady=10)
        box2.pack(fill=tk.X, pady=6)

        row2 = tk.Frame(box2, bg=THEME["card_bg"])
        row2.pack(fill=tk.X)
        tk.Label(row2, text="随机最小等待:", font=("Microsoft YaHei UI", 9), bg=THEME["card_bg"]).pack(side=tk.LEFT)
        self.ent_cooldown_min = tk.Entry(row2, font=("Consolas", 10), width=8, relief=tk.SOLID, bd=1)
        self.ent_cooldown_min.pack(side=tk.LEFT, padx=(6, 12))
        self.ent_cooldown_min.insert(0, str(self.cfg.get("MIN_COOLDOWN_SEC", 25)))

        tk.Label(row2, text="随机最大等待:", font=("Microsoft YaHei UI", 9), bg=THEME["card_bg"]).pack(side=tk.LEFT)
        self.ent_cooldown_max = tk.Entry(row2, font=("Consolas", 10), width=8, relief=tk.SOLID, bd=1)
        self.ent_cooldown_max.pack(side=tk.LEFT, padx=(6, 10))
        self.ent_cooldown_max.insert(0, str(self.cfg.get("MAX_COOLDOWN_SEC", 45)))
        tk.Label(box2, text="建议保持在 20 秒以上，模拟真实人工逐个搜索申请习惯", font=("Microsoft YaHei UI", 8), fg="#059669", bg=THEME["card_bg"]).pack(anchor="w", pady=(6, 0))

        # 3. 动作微停顿
        box3 = tk.LabelFrame(content_f, text=" 动作间随机拟人停顿 (秒) ", font=("Microsoft YaHei UI", 9, "bold"), bg=THEME["card_bg"], fg=THEME["text_main"], padx=15, pady=10)
        box3.pack(fill=tk.X, pady=6)

        row3 = tk.Frame(box3, bg=THEME["card_bg"])
        row3.pack(fill=tk.X)
        tk.Label(row3, text="动作最小停顿:", font=("Microsoft YaHei UI", 9), bg=THEME["card_bg"]).pack(side=tk.LEFT)
        self.ent_pause_min = tk.Entry(row3, font=("Consolas", 10), width=8, relief=tk.SOLID, bd=1)
        self.ent_pause_min.pack(side=tk.LEFT, padx=(6, 12))
        self.ent_pause_min.insert(0, str(self.cfg.get("ACTION_PAUSE_MIN", 1.2)))

        tk.Label(row3, text="动作最大停顿:", font=("Microsoft YaHei UI", 9), bg=THEME["card_bg"]).pack(side=tk.LEFT)
        self.ent_pause_max = tk.Entry(row3, font=("Consolas", 10), width=8, relief=tk.SOLID, bd=1)
        self.ent_pause_max.pack(side=tk.LEFT, padx=(6, 10))
        self.ent_pause_max.insert(0, str(self.cfg.get("ACTION_PAUSE_MAX", 2.0)))
        tk.Label(box3, text="搜号/点击/填表单步骤之间的随机短休眠，建议 1.0 ~ 2.5 秒", font=("Microsoft YaHei UI", 8), fg="#059669", bg=THEME["card_bg"]).pack(anchor="w", pady=(6, 0))

        # 底部操作按钮
        btn_row = tk.Frame(self, bg=THEME["card_bg"], padx=20, pady=12)
        btn_row.pack(fill=tk.X, side="bottom")

        ModernButton(btn_row, text="保存配置", command=self.on_save, bg=THEME["primary"], hover_bg=THEME["primary_hover"]).pack(side=tk.RIGHT, padx=5)
        ModernButton(btn_row, text="取消", command=self.destroy, bg="#E5E7EB", hover_bg="#D1D5DB", fg="#374151").pack(side=tk.RIGHT, padx=5)

    def on_save(self):
        try:
            daily_max = int(self.ent_daily_max.get().strip())
            c_min = int(self.ent_cooldown_min.get().strip())
            c_max = int(self.ent_cooldown_max.get().strip())
            p_min = float(self.ent_pause_min.get().strip())
            p_max = float(self.ent_pause_max.get().strip())
        except ValueError:
            messagebox.showerror("格式错误", "输入参数格式不合法，请检查是否填写了非数字字符！")
            return

        if daily_max <= 0:
            messagebox.showerror("参数错误", "单日添加上限必须大于 0！")
            return
        if c_min <= 0 or c_max <= 0 or c_min > c_max:
            messagebox.showerror("参数错误", "冷却时间设置错误：最小时间必须小于等于最大时间，且均需大于 0！")
            return
        if p_min <= 0 or p_max <= 0 or p_min > p_max:
            messagebox.showerror("参数错误", "动作微停顿设置错误：最小停顿必须小于等于最大停顿，且均需大于 0！")
            return

        new_cfg = {
            "DAILY_MAX_LIMIT": daily_max,
            "MIN_COOLDOWN_SEC": c_min,
            "MAX_COOLDOWN_SEC": c_max,
            "ACTION_PAUSE_MIN": p_min,
            "ACTION_PAUSE_MAX": p_max,
            "SEARCH_DEBOUNCE": self.cfg.get("SEARCH_DEBOUNCE", 1.0),
            "PAGE_SIZE": self.cfg.get("PAGE_SIZE", 15)  # 保持既有 PAGE_SIZE 不被覆盖丢失
        }

        save_safety_config(new_cfg)
        if self.on_save_callback:
            self.on_save_callback(new_cfg)

        self.log(f"🛡️【安全参数已更新】单日上限: {daily_max} | 冷却区间: {c_min}~{c_max}s | 拟人停顿: {p_min}~{p_max}s")
        messagebox.showinfo("成功", "安全风控与拟人参数已更新生效！")
        self.destroy()
