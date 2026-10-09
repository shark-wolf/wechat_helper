import re
import tkinter as tk
import pandas as pd
from config import THEME

def parse_placeholders(template_str: str, row_dict: dict) -> str:
    """解析 ${列名} 格式的动态占位符"""
    if not template_str:
        return ""

    def replacer(match):
        col_name = match.group(1).strip()
        val = row_dict.get(col_name, "")
        if pd.isna(val) or val is None or str(val).strip() in ["", "-", "nan", "None"]:
            return ""
        return str(val).strip()

    res = re.sub(r"\$\{([^}]+)\}", replacer, template_str)
    # 优化多余分隔符，如连续两个 - 变为一个 -，并剔除首尾多余分隔符
    res = re.sub(r"-+", "-", res).strip("-")
    return res

class ModernButton(tk.Label):
    """自定义现代化 Hover 态按钮组件"""
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
