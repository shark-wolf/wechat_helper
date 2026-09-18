import os
import sys
import json

# 兼容打包单文件环境与开发源码运行环境
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ICON_PATH = os.path.join(BASE_DIR, "app_icon.ico")
COORDS_FILE = os.path.join(BASE_DIR, "coords_config.json")
TEMPLATE_CONFIG_FILE = os.path.join(BASE_DIR, "template_config.json")
APP_USER_MODEL_ID = "company.wechat.automation.pro.4.0"

SAFETY_CONFIG = {
    "DAILY_MAX_LIMIT": 15,
    "MIN_COOLDOWN_SEC": 25,
    "MAX_COOLDOWN_SEC": 45,
    "ACTION_PAUSE_MIN": 1.2,
    "ACTION_PAUSE_MAX": 2.0,
    "SEARCH_DEBOUNCE": 0.5
}

STEPS = [
    ("CONNECT", "1. 唤醒并置顶 PC 微信主窗口"),
    ("SEARCH", "2. 静默定位搜索框，键入手机号+下键+回车"),
    ("CHECK_CARD", "3. 状态闭环双探视频号并点击『添加到通讯录』"),
    ("SEND_VERIFY", "4. 填写验证申请语及备注并确认发送")
]

GREETING_POOL = [
    "你好，我是通过电话联系你的",
    "您好，之前存了您的电话，加个微信",
    "你好，看到电话过来加一下",
    "您好，沟通一下业务，方便通过下吗",
    "你好，加微信方便后续沟通",
    "您好，同行交流，方便通过一下吗"
]

# 默认表头与动态字段映射配置
DEFAULT_TEMPLATE_CONFIG = {
    "headers": ["手机号", "客户姓名", "申请打招呼语", "微信备注"],
    "phone_col": "手机号",
    "greeting_col": "申请打招呼语",
    "remark_col": "微信备注"
}

def load_template_config() -> dict:
    cfg = DEFAULT_TEMPLATE_CONFIG.copy()
    if os.path.exists(TEMPLATE_CONFIG_FILE):
        try:
            with open(TEMPLATE_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                cfg.update(saved)
        except Exception:
            pass
    return cfg

def save_template_config(cfg: dict):
    try:
        with open(TEMPLATE_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# 实测默认基准坐标
DEFAULT_COORDS = {
    "STEP3_NO_CHANNELS": [276, 414],     # 步骤3-无视频号按钮[cite: 1]
    "STEP3_HAS_CHANNELS": [284, 497],    # 步骤3-有视频号按钮
    "STEP4_GREETING_INPUT": [190, 160],  # 步骤4-招呼语输入框
    "STEP4_REMARK_INPUT": [190, 280],    # 步骤4-备注输入框
    "STEP4_CONFIRM_BTN": [145, 705]      # 步骤4-确定按钮
}

def load_coords() -> dict:
    coords = DEFAULT_COORDS.copy()
    if os.path.exists(COORDS_FILE):
        try:
            with open(COORDS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                coords.update(saved)
        except Exception:
            pass
    return coords

def save_coord(key: str, rel_x: int, rel_y: int):
    coords = load_coords()
    coords[key] = [rel_x, rel_y]
    try:
        with open(COORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(coords, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

THEME = {
    "bg": "#F5F7FA",
    "card_bg": "#FFFFFF",
    "text_main": "#1F2937",
    "text_sub": "#6B7280",
    "primary": "#07C160",
    "primary_hover": "#06AD56",
    "accent": "#2563EB",
    "accent_hover": "#1D4ED8",
    "warning": "#DC2626",
    "warning_hover": "#B91C1C",
    "border": "#E5E7EB",
    "disabled_bg": "#E5E7EB",
    "disabled_fg": "#9CA3AF"
}

PAGE_SIZE = 15
