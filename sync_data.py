# sync_data.py
# 本地定时同步脚本：导出 MySQL 视图数据到 CSV → git push 到 GitHub
# 配合 Windows 任务计划程序定时运行，实现 Streamlit Cloud 准实时更新
#
# 用法:
#   python sync_data.py              # 完整同步（导出 + git push）
#   python sync_data.py --dry-run    # 只导出不推送，测试用
#   python sync_data.py --etl        # 先执行 ETL 刷新存储过程，再导出推送

import os
import sys
import subprocess
import traceback
from datetime import datetime
from pathlib import Path

# 修复 Windows 控制台编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

# ============================================
# 配置
# ============================================

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "mysql"),
}

# 要导出的视图列表 (SQL视图名, CSV文件名)
EXPORT_VIEWS = [
    ("v_decision_daily",        "v_decision_daily.csv"),
    ("v_decision_outflow_daily", "v_decision_outflow_daily.csv"),
    ("v_payment_inflow_daily",   "v_payment_inflow_daily.csv"),
    ("v_payment_outflow_daily",  "v_payment_outflow_daily.csv"),
]

# CSV 输出目录
EXPORT_DIR = Path(__file__).parent / "data" / "export"

# ETL 刷新的存储过程
ETL_PROCEDURES = [
    "refresh_decision_inflow",
    "refresh_decision_outflow",
    "refresh_payment_inflow",
    "refresh_payment_outflow",
]


# ============================================
# 工具函数
# ============================================

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def get_engine():
    cfg = DB_CONFIG
    url = (
        f"mysql+pymysql://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['database']}?charset=utf8mb4"
    )
    return create_engine(url)


# ============================================
# 核心步骤
# ============================================

def run_etl(engine):
    """执行 ETL 存储过程刷新视图"""
    from sqlalchemy import text
    log("开始执行 ETL 刷新存储过程...")
    with engine.connect() as conn:
        for proc in ETL_PROCEDURES:
            try:
                log(f"  执行 CALL {proc}() ...")
                conn.execute(text(f"CALL {proc}()"))
                conn.commit()
                log(f"  [OK] {proc} done")
            except Exception as e:
                log(f"  [FAIL] {proc}: {e}", "ERROR")
    log("ETL refresh done")


def export_data(engine):
    """导出所有视图到 CSV"""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for view_name, csv_name in EXPORT_VIEWS:
        try:
            log(f"导出 {view_name} ...")
            df = pd.read_sql(f"SELECT * FROM {view_name}", engine)
            csv_path = EXPORT_DIR / csv_name
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            log(f"  [OK] {view_name} -> {csv_name}  ({len(df)} rows, {len(df.columns)} cols)")
            results.append((view_name, len(df), True, ""))
        except Exception as e:
            log(f"  [FAIL] {view_name}: {e}", "ERROR")
            results.append((view_name, 0, False, str(e)))

    return results


def git_push():
    """git add + commit + push"""
    project_root = Path(__file__).parent
    os.chdir(project_root)

    if not (project_root / ".git").exists():
        log("当前目录不是 git 仓库，跳过推送", "WARN")
        return False

    try:
        subprocess.run(["git", "add", "data/export/"], check=True, capture_output=True)

        status = subprocess.run(
            ["git", "status", "--porcelain", "data/export/"],
            capture_output=True, text=True
        )
        if not status.stdout.strip():
            log("数据无变化，跳过推送")
            return True

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subprocess.run(
            ["git", "commit", "-m", f"data: auto sync {ts}"],
            check=True, capture_output=True
        )
        log("已提交 commit")

        result = subprocess.run(["git", "push"], capture_output=True, text=True)
        if result.returncode == 0:
            log("[OK] pushed to GitHub")
            return True
        else:
            log(f"git push 失败: {result.stderr}", "ERROR")
            return False

    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        log(f"git 操作失败: {err}", "ERROR")
        return False


# ============================================
# 主流程
# ============================================

def main():
    dry_run = "--dry-run" in sys.argv
    run_etl_flag = "--etl" in sys.argv

    log("=" * 50)
    log("开始数据同步")
    log(f"模式: {'dry-run' if dry_run else '完整同步'}")
    log(f"ETL刷新: {'是' if run_etl_flag else '否'}")
    log(f"数据库: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    log("=" * 50)

    # 1. 连接数据库
    try:
        engine = get_engine()
        log("数据库连接成功")
    except Exception as e:
        log(f"数据库连接失败: {e}", "ERROR")
        traceback.print_exc()
        sys.exit(1)

    # 2. ETL 刷新（可选）
    if run_etl_flag:
        try:
            run_etl(engine)
        except Exception as e:
            log(f"ETL 刷新出错，继续导出: {e}", "WARN")

    # 3. 导出数据
    results = export_data(engine)

    success = sum(1 for _, _, ok, _ in results if ok)
    fail = sum(1 for _, _, ok, _ in results if not ok)
    log(f"导出完成: {success} 成功, {fail} 失败")

    if dry_run:
        log(f"dry-run 模式，CSV 文件在: {EXPORT_DIR}")
        log("同步结束（未推送）")
        return

    # 4. git push
    if fail == len(EXPORT_VIEWS):
        log("全部导出失败，跳过推送", "WARN")
    else:
        git_push()

    log("同步结束")
    log("=" * 50)


if __name__ == "__main__":
    main()
