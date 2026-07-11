# dashboard.py
import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from pathlib import Path

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(page_title="决策付款驾驶舱", layout="wide")

# ============================================================
# 数据加载：本地用数据库，云端用CSV（自动检测）
# ============================================================
CSV_DIR = Path("data/export")
DB_MODE = False
engine = None

if Path(".env").exists():
    try:
        from dotenv import load_dotenv
        load_dotenv()
        DB_CONFIG = {
            "host": os.getenv("DB_HOST", "localhost"),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", "123456"),
            "database": os.getenv("DB_NAME", "mysql"),
            "charset": "utf8mb4"
        }
        DATABASE_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}?charset=utf8mb4"
        engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        DB_MODE = True
    except Exception:
        DB_MODE = False
        engine = None


@st.cache_data(ttl=3600)
def load_data():
    if DB_MODE:
        df_inflow = pd.read_sql("SELECT * FROM v_decision_daily", engine)
        df_outflow = pd.read_sql("SELECT * FROM v_decision_outflow_daily", engine)
        df_payment_in = pd.read_sql("SELECT * FROM v_payment_inflow_daily", engine)
        df_payment_out = pd.read_sql("SELECT * FROM v_payment_outflow_daily", engine)
    else:
        df_inflow = pd.read_csv(CSV_DIR / "v_decision_daily.csv")
        df_outflow = pd.read_csv(CSV_DIR / "v_decision_outflow_daily.csv")
        df_payment_in = pd.read_csv(CSV_DIR / "v_payment_inflow_daily.csv")
        df_payment_out = pd.read_csv(CSV_DIR / "v_payment_outflow_daily.csv")

    # ---- 日期解析 ----
    for df in [df_inflow, df_outflow]:
        df["提交申请时间"] = pd.to_datetime(df["提交申请时间"], errors="coerce")
        df["审批完成时间"] = pd.to_datetime(df["审批完成时间"], errors="coerce")

    for df in [df_payment_in, df_payment_out]:
        df["付款申请时间"] = pd.to_datetime(df["付款申请时间"], errors="coerce")

    df_payment_in["付款时间"] = pd.to_datetime(df_payment_in["付款时间"], errors="coerce")
    df_payment_out["有效付款时间"] = pd.to_datetime(df_payment_out["有效付款时间"], errors="coerce")
    if "图远付款时间" in df_payment_out.columns:
        df_payment_out["图远付款时间"] = pd.to_datetime(df_payment_out["图远付款时间"], errors="coerce")

    # ---- 数值列 ----
    df_inflow["套数"] = pd.to_numeric(df_inflow["套数"], errors="coerce").fillna(0)
    df_outflow["套数"] = pd.to_numeric(df_outflow["套数"], errors="coerce").fillna(0)
    df_payment_in["回购金额"] = pd.to_numeric(df_payment_in["回购金额"], errors="coerce").fillna(0)
    df_payment_out["回购金额"] = pd.to_numeric(df_payment_out["回购金额"], errors="coerce").fillna(0)

    # ---- 决策审批时长（审批完成时间 - 提交申请时间，单位：天）----
    df_outflow["决策审批时长"] = (
        df_outflow["审批完成时间"] - df_outflow["提交申请时间"]
    ).dt.total_seconds() / 86400

    # ---- 付款时长（有效付款时间 - 付款申请时间，单位：天）----
    df_payment_out["付款时长"] = (
        df_payment_out["有效付款时间"] - df_payment_out["付款申请时间"]
    ).dt.total_seconds() / 86400

    # ---- 提取月份 ----
    df_inflow["月份"] = df_inflow["提交申请时间"].dt.strftime("%Y年%m月")
    df_outflow["月份"] = df_outflow["审批完成时间"].dt.strftime("%Y年%m月")
    df_payment_in["月份"] = df_payment_in["付款申请时间"].dt.strftime("%Y年%m月")
    df_payment_out["月份"] = df_payment_out["有效付款时间"].dt.strftime("%Y年%m月")

    # ---- 提取年份（用于透视表筛选2026年）----
    df_inflow["年份"] = df_inflow["提交申请时间"].dt.year
    df_outflow["年份"] = df_outflow["审批完成时间"].dt.year
    df_payment_in["年份"] = df_payment_in["付款申请时间"].dt.year
    df_payment_out["年份"] = df_payment_out["有效付款时间"].dt.year

    return df_inflow, df_outflow, df_payment_in, df_payment_out


# ============================================================
# 组别/区域映射
# ============================================================
GROUP_MAP = {
    "事业二部一组": ["张磊磊", "秦凯琪", "范雨农"],
    "事业二部二组": ["尚勇磊", "张旺龙", "田若成"],
    "事业二部三组": ["王晓琪", "白昊昊", "白吴昊", "郭利明", "马琛超"],
    "事业二部四组": ["何穆", "宋晋", "王方泰", "蒙迪"],
    "事业二部五组": ["张洲培", "朱子煜", "陈毓甲"],
}

REGION_MAP = {
    "事业二部一组": "山西",
    "事业二部二组": "山西",
    "事业二部三组": "山西",
    "事业二部四组": "陕西",
    "事业二部五组": "陕西",
}

ALL_GROUPS = list(GROUP_MAP.keys())
ALL_REGIONS = ["山西", "陕西"]


def get_group(name):
    """根据人名匹配组别（支持后缀匹配，如 '白昊昊-晋城宏达' → '事业二部三组'）"""
    if pd.isna(name) or not str(name).strip():
        return "其他"
    name_str = str(name)
    for group, members in GROUP_MAP.items():
        for member in members:
            if name_str.startswith(member):
                return group
    return "其他"


def get_region(group):
    return REGION_MAP.get(group, "其他")


# ============================================================
# 加载数据
# ============================================================
with st.spinner("加载数据中..."):
    df_inflow, df_outflow, df_payment_in, df_payment_out = load_data()

    # 应用组别/区域映射
    df_inflow["组别"] = df_inflow["申请人"].apply(get_group)
    df_inflow["区域"] = df_inflow["组别"].apply(get_region)

    df_outflow["组别"] = df_outflow["申请人"].apply(get_group)
    df_outflow["区域"] = df_outflow["组别"].apply(get_region)
    df_outflow["所属部门"] = df_outflow["组别"]

    df_payment_in["组别"] = df_payment_in["项目经理名称"].apply(get_group)
    df_payment_in["区域"] = df_payment_in["组别"].apply(get_region)

    df_payment_out["组别"] = df_payment_out["项目经理名称"].apply(get_group)
    df_payment_out["区域"] = df_payment_out["组别"].apply(get_region)

# 数据源标识
if DB_MODE:
    st.sidebar.info("数据源：本地数据库")
else:
    st.sidebar.info("数据源：CSV文件")

# ============================================================
# 侧边栏筛选器
# ============================================================
st.sidebar.title("筛选器")

# 区域筛选
selected_regions = st.sidebar.multiselect("区域", ALL_REGIONS, default=ALL_REGIONS)

# 组别筛选
group_options = [g for g in ALL_GROUPS if REGION_MAP.get(g, "") in selected_regions]
if not group_options:
    group_options = ALL_GROUPS
selected_groups = st.sidebar.multiselect("组别", ALL_GROUPS, default=ALL_GROUPS)


# ============================================================
# 数据过滤
# ============================================================
def filter_df(df):
    if df.empty:
        return df
    result = df.copy()
    if selected_regions:
        result = result[result["区域"].isin(selected_regions)]
    if selected_groups:
        result = result[result["组别"].isin(selected_groups)]
    return result


df_inflow_f = filter_df(df_inflow)
df_outflow_f = filter_df(df_outflow)
df_payment_in_f = filter_df(df_payment_in)
df_payment_out_f = filter_df(df_payment_out)

# ============================================================
# 页面 Tab
# ============================================================
tab1, tab2 = st.tabs(["驾驶舱", "数据透视表"])

# ============================================================
# 第一页：驾驶舱
# ============================================================
with tab1:
    # ===== 一、核心指标 =====
    st.markdown("## 核心指标")

    # --- 决策情况 ---
    st.markdown("### 决策情况")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        val = df_inflow_f["决策编号"].nunique() if not df_inflow_f.empty else 0
        st.metric("决策流入条数", f"{val:,}")
    with col2:
        val = df_inflow_f["套数"].sum() if not df_inflow_f.empty else 0
        st.metric("决策流入套数", f"{val:,.0f}")
    with col3:
        val = df_outflow_f["决策编号"].nunique() if not df_outflow_f.empty else 0
        st.metric("决策流出条数", f"{val:,}")
    with col4:
        val = df_outflow_f["套数"].sum() if not df_outflow_f.empty else 0
        st.metric("决策流出套数", f"{val:,.0f}")
    with col5:
        val = df_outflow_f["决策审批时长"].mean() if not df_outflow_f.empty and "决策审批时长" in df_outflow_f.columns else 0
        st.metric("决策审批时长", f"{val:.1f} 天")

    # --- 付款情况 ---
    st.markdown("### 付款情况")
    col6, col7, col8, col9, col10 = st.columns(5)

    with col6:
        val = df_payment_in_f["回购业务编号"].nunique() if not df_payment_in_f.empty else 0
        st.metric("付款流入条数", f"{val:,}")
    with col7:
        val = len(df_payment_in_f) if not df_payment_in_f.empty else 0
        st.metric("付款流入套数", f"{val:,}")
    with col8:
        val = df_payment_out_f["回购业务编号"].nunique() if not df_payment_out_f.empty else 0
        st.metric("付款流出条数", f"{val:,}")
    with col9:
        val = len(df_payment_out_f) if not df_payment_out_f.empty else 0
        st.metric("付款流出套数", f"{val:,}")
    with col10:
        val = df_payment_out_f["付款时长"].mean() if not df_payment_out_f.empty and "付款时长" in df_payment_out_f.columns else 0
        st.metric("付款时长", f"{val:.1f} 天")

    # ===== 二、趋势分析 =====
    st.markdown("---")
    st.markdown("## 趋势分析")

    col11, col12 = st.columns(2)

    with col11:
        # 决策流入流出套数月度折线图
        _in = df_inflow_f.dropna(subset=["月份"]) if not df_inflow_f.empty else df_inflow_f
        _out = df_outflow_f.dropna(subset=["月份"]) if not df_outflow_f.empty else df_outflow_f
        inflow_monthly = _in.groupby("月份")["套数"].sum().reset_index() if not _in.empty else pd.DataFrame(columns=["月份", "套数"])
        outflow_monthly = _out.groupby("月份")["套数"].sum().reset_index() if not _out.empty else pd.DataFrame(columns=["月份", "套数"])

        fig_trend1 = go.Figure()
        if not inflow_monthly.empty:
            fig_trend1.add_trace(go.Scatter(
                x=inflow_monthly["月份"], y=inflow_monthly["套数"],
                mode="lines+markers", name="决策流入",
                line=dict(color="#1f77b4", width=3)
            ))
        if not outflow_monthly.empty:
            fig_trend1.add_trace(go.Scatter(
                x=outflow_monthly["月份"], y=outflow_monthly["套数"],
                mode="lines+markers", name="决策流出",
                line=dict(color="#ff7f0e", width=3)
            ))
        fig_trend1.update_layout(
            title="决策流入流出套数月度趋势",
            xaxis_title="月份", yaxis_title="套数",
            height=350, hovermode="x unified"
        )
        st.plotly_chart(fig_trend1, use_container_width=True)

    with col12:
        # 付款流入流出套数月度折线图
        _pin = df_payment_in_f.dropna(subset=["月份"]) if not df_payment_in_f.empty else df_payment_in_f
        _pout = df_payment_out_f.dropna(subset=["月份"]) if not df_payment_out_f.empty else df_payment_out_f
        pay_in_monthly = _pin.groupby("月份").size().reset_index(name="套数") if not _pin.empty else pd.DataFrame(columns=["月份", "套数"])
        pay_out_monthly = _pout.groupby("月份").size().reset_index(name="套数") if not _pout.empty else pd.DataFrame(columns=["月份", "套数"])

        fig_trend2 = go.Figure()
        if not pay_in_monthly.empty:
            fig_trend2.add_trace(go.Scatter(
                x=pay_in_monthly["月份"], y=pay_in_monthly["套数"],
                mode="lines+markers", name="付款流入",
                line=dict(color="#2ca02c", width=3)
            ))
        if not pay_out_monthly.empty:
            fig_trend2.add_trace(go.Scatter(
                x=pay_out_monthly["月份"], y=pay_out_monthly["套数"],
                mode="lines+markers", name="付款流出",
                line=dict(color="#d62728", width=3)
            ))
        fig_trend2.update_layout(
            title="付款流入流出套数月度趋势",
            xaxis_title="月份", yaxis_title="套数",
            height=350, hovermode="x unified"
        )
        st.plotly_chart(fig_trend2, use_container_width=True)

    # ===== 三、部门区域占比分析 =====
    st.markdown("---")
    st.markdown("## 部门区域占比分析")

    def make_pie_chart(df, value_col, group_col, title, is_count=False):
        """生成饼图，显示百分比和具体套数"""
        if df.empty:
            fig = go.Figure()
            fig.update_layout(title=f"{title}（无数据）", height=320)
            return fig

        if is_count:
            # 付款数据：套数 = 行数
            pie_data = df.groupby(group_col).size().reset_index(name="套数")
        else:
            # 决策数据：套数 = 套数列求和
            pie_data = df.groupby(group_col)[value_col].sum().reset_index()
            pie_data = pie_data.rename(columns={value_col: "套数"})

        # 排除"其他"
        pie_data = pie_data[pie_data[group_col] != "其他"]

        if pie_data.empty:
            fig = go.Figure()
            fig.update_layout(title=f"{title}（无数据）", height=320)
            return fig

        fig = px.pie(
            pie_data, values="套数", names=group_col,
            title=title, height=320
        )
        fig.update_traces(
            textinfo="label+percent+value",
            textfont_size=12
        )
        return fig

    # --- 按组别饼图 ---
    st.markdown("### 按组别占比")
    col13, col14 = st.columns(2)
    with col13:
        st.plotly_chart(make_pie_chart(df_inflow_f, "套数", "组别", "决策流入套数 - 按组别"), use_container_width=True)
    with col14:
        st.plotly_chart(make_pie_chart(df_outflow_f, "套数", "组别", "决策流出套数 - 按组别"), use_container_width=True)

    col15, col16 = st.columns(2)
    with col15:
        st.plotly_chart(make_pie_chart(df_payment_in_f, None, "组别", "付款流入套数 - 按组别", is_count=True), use_container_width=True)
    with col16:
        st.plotly_chart(make_pie_chart(df_payment_out_f, None, "组别", "付款流出套数 - 按组别", is_count=True), use_container_width=True)

    # --- 按区域饼图 ---
    st.markdown("### 按区域占比")
    col17, col18 = st.columns(2)
    with col17:
        st.plotly_chart(make_pie_chart(df_inflow_f, "套数", "区域", "决策流入套数 - 按区域"), use_container_width=True)
    with col18:
        st.plotly_chart(make_pie_chart(df_outflow_f, "套数", "区域", "决策流出套数 - 按区域"), use_container_width=True)

    col19, col20 = st.columns(2)
    with col19:
        st.plotly_chart(make_pie_chart(df_payment_in_f, None, "区域", "付款流入套数 - 按区域", is_count=True), use_container_width=True)
    with col20:
        st.plotly_chart(make_pie_chart(df_payment_out_f, None, "区域", "付款流出套数 - 按区域", is_count=True), use_container_width=True)

    # ===== 四、明细数据 =====
    st.markdown("---")
    st.markdown("## 明细数据")

    detail_type = st.radio(
        "选择查看明细",
        ["决策流入报表", "决策流出报表", "付款流入报表", "付款流出报表"],
        horizontal=True
    )

    if detail_type == "决策流入报表":
        show_cols = [c for c in ["年月周数", "月份", "决策编号", "套数", "主体", "申请人", "组别", "区域", "提交申请时间", "审批类型", "流程状态"] if c in df_inflow_f.columns]
        detail_df = df_inflow_f[show_cols] if not df_inflow_f.empty else pd.DataFrame()
    elif detail_type == "决策流出报表":
        show_cols = [c for c in ["年月周数", "月份", "决策编号", "套数", "主体", "申请人", "组别", "区域", "提交申请时间", "审批完成时间", "决策审批时长", "审批类型"] if c in df_outflow_f.columns]
        detail_df = df_outflow_f[show_cols] if not df_outflow_f.empty else pd.DataFrame()
    elif detail_type == "付款流入报表":
        show_cols = [c for c in ["年月周数", "月份", "付款申请编号", "回购业务编号", "所属部门", "项目经理名称", "组别", "区域", "回购金额", "电池SN", "电池型号", "车辆品牌", "付款申请时间", "付款时间"] if c in df_payment_in_f.columns]
        detail_df = df_payment_in_f[show_cols] if not df_payment_in_f.empty else pd.DataFrame()
    else:
        show_cols = [c for c in ["年月周数", "月份", "付款申请编号", "回购业务编号", "所属部门", "项目经理名称", "组别", "区域", "回购金额", "电池SN", "电池型号", "车辆品牌", "付款申请时间", "有效付款时间", "付款时长"] if c in df_payment_out_f.columns]
        detail_df = df_payment_out_f[show_cols] if not df_payment_out_f.empty else pd.DataFrame()

    st.dataframe(detail_df, use_container_width=True, height=400)


# ============================================================
# 第二页：数据透视表
# ============================================================
with tab2:
    st.markdown("## 数据透视表")

    # --- 1-4: 按月度统计各项目经理 ---
    st.markdown("### 按月度统计各项目经理")

    def make_pivot_count(df, name_col, dept_col, value_col, agg_func, title):
        """生成数据透视表"""
        if df.empty:
            st.markdown(f"**{title}**（无数据）")
            return

        work = df.copy()
        # 筛选有效记录
        work = work[work[name_col].notna() & (work[name_col] != "") & work["月份"].notna()]
        if work.empty:
            st.markdown(f"**{title}**（无数据）")
            return

        if agg_func == "nunique":
            pivot = work.pivot_table(
                index=[name_col, dept_col],
                columns="月份",
                values=value_col,
                aggfunc="nunique",
                fill_value=0
            )
        elif agg_func == "size":
            pivot = work.pivot_table(
                index=[name_col, dept_col],
                columns="月份",
                values=value_col,
                aggfunc="size",
                fill_value=0
            )
        else:  # sum
            pivot = work.pivot_table(
                index=[name_col, dept_col],
                columns="月份",
                values=value_col,
                aggfunc="sum",
                fill_value=0
            )

        # 添加总计列
        pivot["总计"] = pivot.sum(axis=1)
        pivot = pivot.sort_values("总计", ascending=False)

        st.markdown(f"**{title}**")
        st.dataframe(pivot, use_container_width=True)
        st.markdown("")

    # 1. 决策流出条数（按月度，按项目经理）
    make_pivot_count(
        df_outflow_f, "申请人", "所属部门",
        "决策编号", "nunique",
        "1. 各项目经理决策流出条数（月度）"
    )

    # 2. 决策流出套数（按月度，按项目经理）
    make_pivot_count(
        df_outflow_f, "申请人", "所属部门",
        "套数", "sum",
        "2. 各项目经理决策流出套数（月度）"
    )

    # 3. 付款流出条数（按月度，按项目经理）
    make_pivot_count(
        df_payment_out_f, "项目经理名称", "所属部门",
        "回购业务编号", "nunique",
        "3. 各项目经理付款流出条数（月度）"
    )

    # 4. 付款流出套数（按月度，按项目经理）
    make_pivot_count(
        df_payment_out_f, "项目经理名称", "所属部门",
        "电池SN", "size",
        "4. 各项目经理付款流出套数（月度）"
    )

    # --- 5-8: 按年月周数统计套数（只保留2026年） ---
    st.markdown("---")
    st.markdown("### 按年月周数统计套数（2026年）")

    def make_weekly_pivot(df, value_col, title, is_count=False):
        """按年月周数统计套数，只保留2026年"""
        if df.empty:
            st.markdown(f"**{title}**（无数据）")
            return

        work = df[df["年份"] == 2026].copy()
        work = work[work["年月周数"].notna()]
        if work.empty:
            st.markdown(f"**{title}**（2026年无数据）")
            return

        if is_count:
            summary = work.groupby("年月周数").size().reset_index(name="套数")
        else:
            summary = work.groupby("年月周数")[value_col].sum().reset_index()
            summary = summary.rename(columns={value_col: "套数"})

        # 添加总计行
        total_row = pd.DataFrame({"年月周数": ["总计"], "套数": [summary["套数"].sum()]})
        summary = pd.concat([summary, total_row], ignore_index=True)

        st.markdown(f"**{title}**")
        st.dataframe(summary, use_container_width=True)
        st.markdown("")

    # 5. 决策流入套数
    make_weekly_pivot(df_inflow_f, "套数", "5. 决策流入套数（2026年）")

    # 6. 决策流出套数
    make_weekly_pivot(df_outflow_f, "套数", "6. 决策流出套数（2026年）")

    # 7. 付款流入套数
    make_weekly_pivot(df_payment_in_f, None, "7. 付款流入套数（2026年）", is_count=True)

    # 8. 付款流出套数
    make_weekly_pivot(df_payment_out_f, None, "8. 付款流出套数（2026年）", is_count=True)


# ============================================================
# 底部
# ============================================================
st.markdown("---")
st.caption(f"数据更新时间：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据来源：{'MySQL' if DB_MODE else 'CSV'}")
