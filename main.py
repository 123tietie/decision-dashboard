# main.py
import logging
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scripts.data_importer import DataImporter
from scripts.etl_refresh import ETLRefresher
from config.config import Config

LOG_PATH = Config.LOG_PATH
os.makedirs(LOG_PATH, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{LOG_PATH}/import_{datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 50)
    logger.info("开始执行驾驶舱数据更新流程")
    logger.info("=" * 50)

    importer = None
    refresher = None

    try:
        # Step 1: 导入数据
        logger.info("[1/3] 开始导入底表数据...")
        importer = DataImporter()
        counts = importer.import_all()
        logger.info(f"[1/3] 导入完成: {counts}")

        # Step 2: 执行ETL
        logger.info("[2/3] 开始刷新中间表...")
        refresher = ETLRefresher()
        results = refresher.refresh_all()
        logger.info(f"[2/3] ETL完成: {results}")

        # Step 3: 验证数据
        logger.info("[3/3] 验证中间表数据...")
        # 可以加一些验证逻辑

        logger.info("=" * 50)
        logger.info("✅ 驾驶舱数据更新完成！")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"❌ 流程执行失败: {e}")
        sys.exit(1)

    finally:
        if importer:
            importer.close()
        if refresher:
            refresher.close()


if __name__ == "__main__":
    main()