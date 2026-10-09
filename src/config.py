import os
import sys
import json

# 兼容单文件 EXE 解压环境与源码运行环境，确保配置持久化在程序同级
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ICON_PATH = os.path.join(BASE_DIR, "app_icon.ico")
COORDS_FILE = os.path.join(BASE_DIR, "coords_config.json")
TEMPLATE_CONFIG_FILE = os.path.join(BASE_DIR, "template_config.json")
SUCCESS_PHONES_FILE = os.path.join(BASE_DIR, "success_phones.json")
SAFETY_CONFIG_FILE = os.path.join(BASE_DIR, "safety_config.json")
APP_USER_MODEL_ID = "company.wechat.automation.pro.4.0"

DEFAULT_SAFETY_CONFIG = {
    # 单日添加上限
    "DAILY_MAX_LIMIT": 100,
    # 单次操作后的拟人随机冷却间隔（单位：秒）
    "MIN_COOLDOWN_SEC": 25,
    "MAX_COOLDOWN_SEC": 45,
    # 动作间随机拟人停顿（单位：秒）
    "ACTION_PAUSE_MIN": 1.2,
    "ACTION_PAUSE_MAX": 2.0,
    # 搜索框输入后的防抖防卡顿时间（单位：秒）
    "SEARCH_DEBOUNCE": 1.0,
    # 表格每页条数
    "PAGE_SIZE": 15
}

def load_safety_config() -> dict:
    cfg = DEFAULT_SAFETY_CONFIG.copy()
    if os.path.exists(SAFETY_CONFIG_FILE):
        try:
            with open(SAFETY_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                cfg.update(saved)
        except Exception:
            pass
    return cfg

def save_safety_config(cfg: dict):
    try:
        with open(SAFETY_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# 全局运行态缓存
SAFETY_CONFIG = load_safety_config()

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

DEFAULT_TEMPLATE_CONFIG = {
    "headers": ["手机号", "姓名", "小区", "楼栋", "单元", "房号"],
    "phone_col": "手机号",
    "greeting_type": "manual",
    "greeting_template": "你好，简单沟通一下！",
    "remark_template": "${小区}${楼栋}${单元}${房号}-${姓名}(${手机号})",
    "dedup_cols": ["手机号", "姓名", "小区", "楼栋", "单元", "房号"]
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

DEFAULT_COORDS = {
    "STEP3_NO_CHANNELS": [276, 414],
    "STEP3_HAS_CHANNELS": [284, 497],
    "STEP4_GREETING_INPUT": [190, 160],
    "STEP4_REMARK_INPUT": [190, 280],
    "STEP4_CONFIRM_BTN": [145, 705]
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

def load_success_phones() -> set:
    if os.path.exists(SUCCESS_PHONES_FILE):
        try:
            with open(SUCCESS_PHONES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(str(p).strip() for p in data if str(p).strip())
        except Exception:
            pass
    return set()

def record_success_phone(phone: str):
    if not phone:
        return
    phone = str(phone).strip()
    phones = load_success_phones()
    phones.add(phone)
    try:
        with open(SUCCESS_PHONES_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(phones)), f, ensure_ascii=False, indent=2)
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

PAGE_SIZE = SAFETY_CONFIG.get("PAGE_SIZE", 15)
