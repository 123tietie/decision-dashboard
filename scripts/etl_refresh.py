# scripts/etl_refresh.py
import logging
from scripts.db_connector import DatabaseConnector

logger = logging.getLogger(__name__)


class ETLRefresher:
    def __init__(self):
        self.db = DatabaseConnector()
        self.db.connect()

    def execute_sql(self, sql):
        """执行SQL语句"""
        try:
            with self.db.conn.cursor() as cur:
                cur.execute(sql)
                self.db.conn.commit()
                logger.info("SQL执行成功")
                return True
        except Exception as e:
            logger.error(f"SQL执行失败: {e}")
            self.db.conn.rollback()
            return False

    def refresh_decision_inflow(self):
        sql = "CALL refresh_decision_inflow();"
        return self.execute_sql(sql)

    def refresh_decision_outflow(self):
        sql = "CALL refresh_decision_outflow();"
        return self.execute_sql(sql)

    def refresh_payment_inflow(self):
        sql = "CALL refresh_payment_inflow();"
        return self.execute_sql(sql)

    def refresh_payment_outflow(self):
        sql = "CALL refresh_payment_outflow();"
        return self.execute_sql(sql)

    def refresh_all(self):
        results = {
            'decision_inflow': self.refresh_decision_inflow(),
            'decision_outflow': self.refresh_decision_outflow(),
            'payment_inflow': self.refresh_payment_inflow(),
            'payment_outflow': self.refresh_payment_outflow(),
        }
        logger.info(f"ETL刷新完成: {results}")
        return results

    def close(self):
        self.db.close()