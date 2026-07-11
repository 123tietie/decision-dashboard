# sync_from_excel.py
# 从 Excel 文件读取源数据，生成 CSV 并推送到 GitHub
#
# 用法:
#   python sync_from_excel.py                          # 自动检测桌面最新 Excel
#   python sync_from_excel.py C:/path/to/711.xlsx      # 指定 Excel 路径
#   python sync_from_excel.py --dry-run                # 只生成 CSV 不推送
#
# 自动检测逻辑: 在 C:/Users/hc/Desktop/决策+付款/ 目录下找最新的 .xlsx 文件
# 适用场景: MySQL 视图数据不准确时，直接用 Excel 源数据生成 CSV

import sys
import os
import glob
import subprocess
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

# ============================================
# 配置
# ============================================

EXPORT_DIR = Path(__file__).parent / "data" / "export"

# Excel sheet -> CSV 文件名映射
SHEET_CSV_MAP = {
    "决策流入": "v_decision_daily.csv",
    "决策流出": "v_decision_outflow_daily.csv",
    "付款流入": "v_payment_inflow_daily.csv",
    "付款流出": "v_payment_outflow_daily.csv",
}

# 每个 CSV 需要的列（按 dashboard.py 要求）
# 格式: { CSV列名: Excel列名 }  None=该列在Excel中不存在，用空值填充
COLUMN_MAP = {
    "v_decision_daily.csv": {
        "决策编号": "决策编号",
        "提交申请时间": "提交申请时间",
        "审批完成时间": "审批完成时间",
        "主体": "主体",
        "审批单名称": "审批单名称",
        "审批类型": "审批类型",
        "流程状态": "流程状态",
        "申请人": "申请人",
        "节点处理时长": "节点处理时长",
        "套数": "套数",
        "年月周数": "年月周数",
    },
    "v_decision_outflow_daily.csv": {
        "决策编号": "决策编号",
        "提交申请时间": "提交申请时间",
        "审批完成时间": "审批完成时间",
        "主体": "主体",
        "审批单名称": "审批单名称",
        "审批类型": "审批类型",
        "流程状态": "流程状态",
        "申请人": "申请人",
        "节点处理时长": "节点处理时长",
        "套数": "套数",
        "年月周数": "年月周数",
        "车辆品牌": None,  # Excel中无此列，留空
    },
    "v_payment_inflow_daily.csv": {
        "付款申请编号": "付款申请编号",
        "回购业务编号": "回购业务编号",
        "回购决策编号": "回购决策编号",
        "所属部门": "所属部门",
        "项目经理名称": "项目经理名称",
        "付款申请时间": "付款申请时间",
        "付款申请状态": "付款申请状态",
        "付款时间": "付款时间",
        "回购金额": "回购金额",
        "已付款金额": "已付款金额",
        "未付款金额": "未付款金额",
        "收款方": "收款方",
        "支付方式": "支付方式",
        "业务状态": "业务状态",
        "付款明细状态": "付款明细状态",
        "当前审批人": "当前审批人",
        "电池型号": "电池型号",
        "电池SN": "电池SN",
        "车辆品牌": "车辆品牌",
        "车架号": "车架号",
        "年月周数": "年月周数",
    },
    "v_payment_outflow_daily.csv": {
        "付款申请编号": "付款申请编号",
        "回购业务编号": "回购业务编号",
        "回购决策编号": "回购决策编号",
        "所属部门": "所属部门",
        "项目经理名称": "项目经理名称",
        "付款申请时间": "付款申请时间",
        "付款申请状态": "付款申请状态",
        "付款时间": "付款时间",
        "回购金额": "回购金额",
        "已付款金额": "已付款金额",
        "未付款金额": "未付款金额",
        "收款方": "收款方",
        "支付方式": "支付方式",
        "业务状态": "业务状态",
        "付款明细状态": "付款明细状态",
        "当前审批人": "当前审批人",
        "电池型号": "电池型号",
        "电池SN": "电池SN",
        "车辆品牌": "车辆品牌",
        "车架号": "车架号",
        "图远付款时间": "图远付款时间",
        "有效付款时间": "_有效日期",  # Excel 中叫 _有效日期
        "年月周数": "年月周数",
    },
}


# 自动检测 Excel 的目录
EXCEL_SEARCH_DIRS = [
    Path("C:/Users/hc/Desktop/决策+付款"),
    Path("C:/Users/hc/Desktop"),
]


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def auto_detect_excel():
    """在桌面目录中自动查找最新的包含决策流入sheet的 Excel 文件"""
    candidates = []
    for search_dir in EXCEL_SEARCH_DIRS:
        if not search_dir.exists():
            continue
        for f in search_dir.glob("*.xlsx"):
            if f.name.startswith("~$"):  # 跳过临时文件
                continue
            candidates.append(f)

    if not candidates:
        return None

    # 按修改时间排序，取最新
    candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    # 验证最新的文件是否包含所需 sheet
    for f in candidates:
        try:
            xl = pd.ExcelFile(f)
            if "决策流入" in xl.sheet_names:
                return str(f)
        except Exception:
            continue

    # 如果都没找到包含决策流入的，返回最新的那个
    return str(candidates[0]) if candidates else None


def convert_excel_to_csv(excel_path):
    """读取 Excel，按 sheet 转换为 CSV"""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    log(f"读取 Excel: {excel_path}")
    xl = pd.ExcelFile(excel_path)
    log(f"Sheet 列表: {xl.sheet_names}")

    results = []

    for sheet_name, csv_name in SHEET_CSV_MAP.items():
        if sheet_name not in xl.sheet_names:
            log(f"  [SKIP] Sheet '{sheet_name}' 不存在", "WARN")
            results.append((sheet_name, 0, False, "sheet not found"))
            continue

        try:
            df = pd.read_excel(xl, sheet_name=sheet_name)
            col_map = COLUMN_MAP[csv_name]

            # 按映射选列
            out_data = {}
            for csv_col, excel_col in col_map.items():
                if excel_col is not None and excel_col in df.columns:
                    out_data[csv_col] = df[excel_col]
                else:
                    out_data[csv_col] = ""

            out_df = pd.DataFrame(out_data)

            csv_path = EXPORT_DIR / csv_name
            out_df.to_csv(csv_path, index=False, encoding="utf-8-sig")

            log(f"  [OK] {sheet_name} -> {csv_name}  ({len(out_df)} rows, {len(out_df.columns)} cols)")

            # 打印关键统计
            if "套数" in out_df.columns:
                try:
                    total = pd.to_numeric(out_df["套数"], errors="coerce").fillna(0).sum()
                    log(f"       套数总计: {total:.0f}")
                except Exception:
                    pass
            else:
                log(f"       行数(套数): {len(out_df)}")

            results.append((sheet_name, len(out_df), True, ""))

        except Exception as e:
            log(f"  [FAIL] {sheet_name}: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            results.append((sheet_name, 0, False, str(e)))

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
            ["git", "commit", "-m", f"data: sync from excel {ts}"],
            check=True, capture_output=True
        )
        log("已提交 commit")

        result = subprocess.run(
            ["git", "push", "origin", "master:main"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            log("[OK] pushed to GitHub")
            return True
        else:
            # SSL 证书问题时的备用方案
            log(f"git push 失败: {result.stderr.strip()}, 尝试禁用 SSL 验证...", "WARN")
            result2 = subprocess.run(
                ["git", "-c", "http.sslVerify=false", "push", "origin", "master:main"],
                capture_output=True, text=True
            )
            if result2.returncode == 0:
                log("[OK] pushed to GitHub (SSL verify disabled)")
                return True
            else:
                log(f"git push 最终失败: {result2.stderr}", "ERROR")
                return False

    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        log(f"git 操作失败: {err}", "ERROR")
        return False


def main():
    dry_run = "--dry-run" in sys.argv

    # 解析 Excel 路径
    excel_path = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            excel_path = arg
            break

    if not excel_path:
        # 自动检测桌面最新 Excel
        excel_path = auto_detect_excel()
        if excel_path:
            log(f"自动检测到 Excel: {excel_path}")
        else:
            # 检查默认路径
            default_path = Path(__file__).parent / "data" / "source.xlsx"
            if default_path.exists():
                excel_path = str(default_path)
            else:
                log("未指定 Excel 文件路径，自动检测失败", "ERROR")
                log("请将 Excel 文件放到 C:/Users/hc/Desktop/决策+付款/ 目录")
                log("或手动指定: python sync_from_excel.py <excel路径>")
                sys.exit(1)

    if not Path(excel_path).exists():
        log(f"文件不存在: {excel_path}", "ERROR")
        sys.exit(1)

    log("=" * 50)
    log("开始从 Excel 同步数据")
    log(f"Excel: {excel_path}")
    log(f"模式: {'dry-run' if dry_run else '完整同步'}")
    log("=" * 50)

    # 1. 转换
    results = convert_excel_to_csv(excel_path)

    success = sum(1 for _, _, ok, _ in results if ok)
    fail = sum(1 for _, _, ok, _ in results if not ok)
    log(f"转换完成: {success} 成功, {fail} 失败")

    if dry_run:
        log(f"dry-run 模式，CSV 文件在: {EXPORT_DIR}")
        log("同步结束（未推送）")
        return

    # 2. git push
    if fail == len(SHEET_CSV_MAP):
        log("全部转换失败，跳过推送", "WARN")
    else:
        git_push()

    log("同步结束")
    log("=" * 50)


if __name__ == "__main__":
    main()
