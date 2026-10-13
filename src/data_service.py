import os
import time
import pandas as pd
from config import FIXED_HEADERS, FIXED_PHONE_COL, load_success_phones
from ui_components import parse_placeholders

class DataService:
    """数据处理与 Excel I/O 服务"""

    @staticmethod
    def read_excel_file(path: str) -> pd.DataFrame:
        """支持 .xlsx 与 .xls 格式的容错读取"""
        ext = os.path.splitext(path)[1].lower()
        if ext == ".xls":
            try:
                return pd.read_excel(path, header=None, dtype=str, engine="xlrd")
            except ImportError:
                return pd.read_excel(path, header=None, dtype=str)
        return pd.read_excel(path, header=None, dtype=str)

    @staticmethod
    def process_imported_data(cleaned_df: pd.DataFrame, template_cfg: dict) -> tuple[pd.DataFrame, int, int]:
        """清洗后数据注入：计算备注、历史库比对、配置去重"""
        df = cleaned_df.copy()
        if "状态" not in df.columns:
            df["状态"] = "未添加"

        remark_tpl = template_cfg.get("remark_template", "")
        df["微信备注"] = df.apply(lambda r: parse_placeholders(remark_tpl, r.to_dict()), axis=1)

        success_phones = load_success_phones()
        history_matched = 0
        for idx, row in df.iterrows():
            phone = str(row[FIXED_PHONE_COL]).strip()
            if phone in success_phones and str(row["状态"]).strip() in ["未添加", "nan", ""]:
                df.at[idx, "状态"] = "已发送申请(历史)"
                history_matched += 1

        dedup_setting = template_cfg.get("dedup_cols", FIXED_HEADERS)
        valid_dedup_cols = [c for c in dedup_setting if c in df.columns]

        before_count = len(df)
        if valid_dedup_cols:
            df = df.drop_duplicates(subset=valid_dedup_cols, keep="first").reset_index(drop=True)
        after_count = len(df)
        dedup_removed = before_count - after_count

        return df, dedup_removed, history_matched

    @staticmethod
    def export_excel(df: pd.DataFrame, target_path: str):
        """导出处理结果"""
        df.to_excel(target_path, index=False)
