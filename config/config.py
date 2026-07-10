# config/config.py
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # 数据库配置（MySQL版本）
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'your_db'),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'port': os.getenv('DB_PORT', '3306')
    }

    # 文件路径
    DATA_PATH = os.getenv('DATA_PATH', './data/input/')
    LOG_PATH = os.getenv('LOG_PATH', './logs/')