# scripts/db_connector.py
import pymysql
import pandas as pd
from sqlalchemy import create_engine
from config.config import Config
import logging

logger = logging.getLogger(__name__)


class DatabaseConnector:
    def __init__(self):
        self.config = Config.DB_CONFIG
        self.conn = None
        self.engine = None

    def connect(self):
        """建立数据库连接（MySQL）"""
        try:
            # 方式1：使用 pymysql 连接
            self.conn = pymysql.connect(
                host=self.config['host'],
                database=self.config['database'],
                user=self.config['user'],
                password=self.config['password'],
                port=int(self.config['port']),
                charset='utf8mb4'
            )

            # 创建SQLAlchemy引擎
            self.engine = create_engine(
                f"mysql+pymysql://{self.config['user']}:{self.config['password']}"
                f"@{self.config['host']}:{self.config['port']}/{self.config['database']}?charset=utf8mb4"
            )

            logger.info("MySQL数据库连接成功")
            return self.conn
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    def execute_query(self, query):
        """执行SQL查询"""
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                if query.strip().upper().startswith('SELECT'):
                    return cur.fetchall()
                self.conn.commit()
                return cur.rowcount
        except Exception as e:
            logger.error(f"查询执行失败: {e}")
            self.conn.rollback()
            raise

    def df_to_db(self, df, table_name, if_exists='replace'):
        """将DataFrame写入MySQL"""
        try:
            df.to_sql(
                table_name,
                self.engine,
                if_exists=if_exists,
                index=False
            )
            logger.info(f"成功写入 {len(df)} 条记录到 {table_name}")
        except Exception as e:
            logger.error(f"写入失败: {e}")
            raise

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("数据库连接已关闭")