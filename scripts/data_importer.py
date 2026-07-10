# scripts/data_importer.py
import pandas as pd
import os
from datetime import datetime, timedelta
import logging
from scripts.db_connector import DatabaseConnector
from config.config import Config

logger = logging.getLogger(__name__)


class DataImporter:  # ← 确保这个类名正确
    def __init__(self):
        self.db = DatabaseConnector()
        self.db.connect()
        self.data_path = Config.DATA_PATH

    @staticmethod
    def get_week_range():
        """计算本周的起止日期"""
        today = datetime.now()
        week_end = today
        week_start = today - timedelta(days=6)
        return week_start.strftime('%Y%m%d'), week_end.strftime('%Y%m%d')

    def import_csv(self, csv_filename: str, table_name: str) -> int:
        """导入单个CSV文件"""
        try:
            file_path = os.path.join(self.data_path, csv_filename)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")

            df = pd.read_csv(file_path, encoding='utf-8')
            logger.info(f"读取 {csv_filename}: {len(df)} 条记录")

            self.db.df_to_db(df, table_name, if_exists='replace')
            return len(df)
        except Exception as e:
            logger.error(f"导入 {csv_filename} 失败: {e}")
            raise

    def import_all(self) -> dict:
        """导入所有底表"""
        week_start, week_end = self.get_week_range()
        logger.info(f"开始导入第 {week_start} - {week_end} 周数据")

        tables = {
            'dpad_table': 'dpad704.csv',
            'payment_table': '付款704.csv',
            'tuyuan_table': '图远704.csv'
        }

        results = {}
        for table_name, filename in tables.items():
            results[table_name] = self.import_csv(filename, table_name)

        logger.info(f"导入完成: {results}")
        return results

    def close(self):
        self.db.close()