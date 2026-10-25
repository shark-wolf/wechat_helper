import time
import random
import threading
from config import FIXED_PHONE_COL, GREETING_POOL, record_success_phone
from ui_components import parse_placeholders

class BatchScheduler:
    """自动化添加调度与风控执行引擎"""

    def __init__(self, bot, log_callback, step_callback, status_callback, counter_callback, get_count_callback=None):
        self.bot = bot
        self.log = log_callback
        self.set_step = step_callback
        self.on_row_updated = status_callback
        self.on_count_incremented = counter_callback
        self.get_current_count = get_count_callback or (lambda: 0)

        self.is_running = False
        self.cancel_requested = False

    def request_stop(self):
        if self.is_running:
            self.cancel_requested = True
            self.log("🛑 正在停止批量任务...")

    def run_single(self, idx: int, df_record: dict, template_cfg: dict):
        threading.Thread(
            target=self._execute_single_pipeline,
            args=(idx, df_record, template_cfg),
            daemon=True
        ).start()

    def run_batch(self, target_indices: list, get_record_func, template_cfg: dict, safety_cfg: dict, on_finished):
        self.is_running = True
        self.cancel_requested = False
        threading.Thread(
            target=self._batch_worker,
            args=(target_indices, get_record_func, template_cfg, safety_cfg, on_finished),
            daemon=True
        ).start()

    def _execute_single_pipeline(self, idx: int, row_dict: dict, template_cfg: dict) -> str:
        phone = str(row_dict.get(FIXED_PHONE_COL, "")).strip()
        greeting_type = template_cfg.get("greeting_type", "manual")
        greeting_tpl = template_cfg.get("greeting_template", "")

        if greeting_type == "manual":
            greeting = parse_placeholders(greeting_tpl, row_dict)
        else:
            pool = template_cfg.get("greetings", GREETING_POOL) or GREETING_POOL
            greeting = random.choice(pool)

        # 获取清洗主页配置好的微信备注与微信标签（默认房东）
        remark = str(row_dict.get("微信备注", "")).strip()
        tag = str(row_dict.get("微信标签", "房东")).strip() or "房东"

        # 调用底层机器人执行添加并自动填入备注与标签
        result = self.bot.execute_add_pipeline(phone, remark_name=remark, custom_greeting=greeting, tag=tag)
        if "成功" in result:
            record_success_phone(phone)
            self.on_count_incremented(phone)

        self.on_row_updated(idx, remark, result)
        return result

    def _batch_worker(self, target_indices, get_record_func, template_cfg, safety_cfg, on_finished):
        self.log(f"🛡️ 启动批量调度，总计: {len(target_indices)} 个任务")
        try:
            daily_limit = int(safety_cfg.get("DAILY_MAX_LIMIT", 100))
        except (ValueError, TypeError):
            daily_limit = 100

        for i, idx in enumerate(target_indices):
            # 1. 检查单日上限与手动停止请求
            current_count = self.get_current_count()
            if self.cancel_requested or current_count >= daily_limit:
                if current_count >= daily_limit:
                    self.log(f"🛑 已达到单日安全上限 {daily_limit} 人，停止批量操作。")
                break

            row_dict = get_record_func(idx)
            phone = str(row_dict.get(FIXED_PHONE_COL, "")).strip()

            self.log(f"👉 [{i+1}/{len(target_indices)}] 准备添加: {phone}")
            result = self._execute_single_pipeline(idx, row_dict, template_cfg)

            # 2. 单个任务刚一结束，立即检测停止指令（实现快速秒停）
            if self.cancel_requested:
                self.log("🛑 已收到停止指令，安全中断后续任务。")
                break

            if any(k in result for k in ["频繁", "限制", "封禁"]):
                self.log("🚨 命中风控熔断，紧急挂起全部任务！")
                break

            # 3. 判断是否成功发送申请
            is_success_sent = "成功" in result

            # 4. 只有在成功发送添加申请后，才执行拟人冷却操作；失败或跳过则直接处理下一个
            if i < len(target_indices) - 1 and not self.cancel_requested and is_success_sent:
                try:
                    c_min = int(safety_cfg.get("MIN_COOLDOWN_SEC", 25))
                    c_max = int(safety_cfg.get("MAX_COOLDOWN_SEC", 45))
                except (ValueError, TypeError):
                    c_min, c_max = 25, 45

                cooldown = random.randint(min(c_min, c_max), max(c_min, c_max))
                for s in range(cooldown, 0, -1):
                    if self.cancel_requested:
                        break
                    if s % 5 == 0 or s <= 3:
                        self.log(f"⏳ 拟人安全冷却剩余 {s} 秒...")
                    time.sleep(1)

        self.is_running = False
        on_finished()
        self.log("🏁 批量任务调度结束。")
