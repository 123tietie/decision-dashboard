# dashboard.py
import os
import streamlit as st
import pandas as pd
import pymysql
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from pathlib import Path

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(page_title="决策付款驾驶舱", layout="wide")

# ============================================================
# 数据库连接（本地） / CSV模式（Streamlit Cloud）
# ============================================================
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "123456"),
    "database": os.getenv("DB_NAME", "mysql"),
    "charset": "utf8mb4"
}

DATABASE_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}?charset=utf8mb4"

# 尝试连接数据库，失败则切换到 CSV 模式
DB_MODE = True
engine = None
try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
except Exception:
    DB_MODE = False
    engine = None

CSV_DIR = Path("data/export")


@st.cache_data(ttl=3600)
def load_data():
    if DB_MODE:
        # ===== 本地模式：直连数据库 =====
        df_inflow = pd.read_sql("SELECT * FROM v_decision_daily", engine)
        df_outflow = pd.read_sql("SELECT * FROM v_decision_outflow_daily", engine)
        df_payment_in = pd.read_sql("SELECT * FROM v_payment_inflow_daily", engine)
        df_payment_out = pd.read_sql("SELECT * FROM v_payment_outflow_daily", engine)
    else:
        # ===== Cloud模式：读CSV =====
        df_inflow = pd.read_csv(CSV_DIR / "v_decision_daily.csv")
        df_outflow = pd.read_csv(CSV_DIR / "v_decision_outflow_daily.csv")
        df_payment_in = pd.read_csv(CSV_DIR / "v_payment_inflow_daily.csv")
        df_payment_out = pd.read_csv(CSV_DIR / "v_payment_outflow_daily.csv")

    # 统一字段名
    df_inflow = df_inflow.rename(columns={
        "决策编号": "决策编号",
        "套数": "套数",
        "主体": "所属部门",
        "申请人": "项目负责人",
        "提交申请时间": "提交申请时间",
        "年月周数": "年月周数"
    })

    df_outflow = df_outflow.rename(columns={
        "决策编号": "决策编号",
        "套数": "套数",
        "主体": "所属部门",
        "申请人": "项目负责人",
        "审批完成时间": "审批完成时间",
        "节点处理时长": "决策审批天数",
        "年月周数": "年月周数"
    })

    df_payment_in = df_payment_in.rename(columns={
        "付款申请编号": "付款编号",
        "回购业务编号": "业务编号",
        "所属部门": "所属部门",
        "项目经理名称": "项目负责人",
        "回购金额": "付款金额",
        "付款申请时间": "付款申请时间",
        "年月周数": "年月周数"
    })

    df_payment_out = df_payment_out.rename(columns={
        "付款申请编号": "付款编号",
        "回购业务编号": "业务编号",
        "所属部门": "所属部门",
        "项目经理名称": "项目负责人",
        "回购金额": "付款金额",
        "有效付款时间": "付款完成时间",
        "年月周数": "年月周数"
    })

    # 确保数值列是数值类型
    df_outflow["决策审批天数"] = pd.to_numeric(df_outflow["决策审批天数"], errors="coerce")

    # 计算付款审批天数
    if "付款申请时间" in df_payment_out.columns and "付款完成时间" in df_payment_out.columns:
        df_payment_out["付款申请时间"] = pd.to_datetime(df_payment_out["付款申请时间"], errors="coerce")
        df_payment_out["付款完成时间"] = pd.to_datetime(df_payment_out["付款完成时间"], errors="coerce")
        df_payment_out["付款审批天数"] = (df_payment_out["付款完成时间"] - df_payment_out["付款申请时间"]).dt.days

    # 确保金额是数值类型
    df_payment_in["付款金额"] = pd.to_numeric(df_payment_in["付款金额"], errors="coerce")
    df_payment_out["付款金额"] = pd.to_numeric(df_payment_out["付款金额"], errors="coerce")
    df_inflow["套数"] = pd.to_numeric(df_inflow["套数"], errors="coerce")
    df_outflow["套数"] = pd.to_numeric(df_outflow["套数"], errors="coerce")

    return df_inflow, df_outflow, df_payment_in, df_payment_out


# ============================================================
# 加载数据
# ============================================================
with st.spinner("加载数据中..."):
    df_inflow, df_outflow, df_payment_in, df_payment_out = load_data()

# 数据源标识
if DB_MODE:
    st.sidebar.info("🔗 数据源：本地数据库")
else:
    st.sidebar.info("📁 数据源：CSV文件")

# ============================================================
# 侧边栏筛选器
# ============================================================
st.sidebar.title("🔍 筛选器")

# 年月周数筛选
week_options = sorted(df_inflow["年月周数"].dropna().unique())
selected_weeks = st.sidebar.multiselect("年月周数", week_options, default=week_options)

# 部门筛选
all_depts = pd.concat([df_inflow["所属部门"], df_payment_in["所属部门"]]).dropna().unique()
dept_options = sorted([d for d in all_depts if d])
selected_depts = st.sidebar.multiselect("所属部门", dept_options, default=dept_options)

# 项目负责人筛选
all_persons = pd.concat([df_inflow["项目负责人"], df_payment_in["项目负责人"]]).dropna().unique()
person_options = sorted([p for p in all_persons if p])
selected_persons = st.sidebar.multiselect("项目负责人", person_options, default=person_options)


# ============================================================
# 数据过滤
# ============================================================
def filter_df(df, week_col="年月周数", dept_col="所属部门", person_col="项目负责人"):
    if df.empty:
        return df
    result = df.copy()
    if selected_weeks and week_col in result.columns:
        result = result[result[week_col].isin(selected_weeks)]
    if selected_depts and dept_col in result.columns:
        result = result[result[dept_col].isin(selected_depts)]
    if selected_persons and person_col in result.columns:
        result = result[result[person_col].isin(selected_persons)]
    return result


df_inflow_f = filter_df(df_inflow)
df_outflow_f = filter_df(df_outflow)
df_payment_in_f = filter_df(df_payment_in)
df_payment_out_f = filter_df(df_payment_out)

# ============================================================
# 计算 KPI 值（处理空值）
# ============================================================
total_in = df_inflow_f["套数"].sum() if not df_inflow_f.empty else 0
total_out = df_outflow_f["套数"].sum() if not df_outflow_f.empty else 0
rate = (total_out / total_in * 100) if total_in > 0 else 0
total_pay_in = df_payment_in_f["付款金额"].sum() if not df_payment_in_f.empty else 0
total_pay_out = df_payment_out_f["付款金额"].sum() if not df_payment_out_f.empty else 0
avg_approval = df_outflow_f["决策审批天数"].mean() if not df_outflow_f.empty and not df_outflow_f[
    "决策审批天数"].isna().all() else 0
pay_avg = df_payment_out_f["付款审批天数"].mean() if not df_payment_out_f.empty and not df_payment_out_f[
    "付款审批天数"].isna().all() else 0
max_approval = df_outflow_f["决策审批天数"].max() if not df_outflow_f.empty and not df_outflow_f[
    "决策审批天数"].isna().all() else 0
max_pay = df_payment_out_f["付款审批天数"].max() if not df_payment_out_f.empty and not df_payment_out_f[
    "付款审批天数"].isna().all() else 0
over_7 = df_outflow_f[df_outflow_f["决策审批天数"] > 7].shape[0] if not df_outflow_f.empty else 0

# ============================================================
# KPI 卡片
# ============================================================
st.markdown("## 📊 核心指标")

col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric("决策流入", f"{total_in:,.0f} 套")
with col2:
    st.metric("决策流出", f"{total_out:,.0f} 套")
with col3:
    st.metric("转化率", f"{rate:.1f}%")
with col4:
    st.metric("付款流入", f"¥{total_pay_in:,.0f}")
with col5:
    st.metric("付款流出", f"¥{total_pay_out:,.0f}")
with col6:
    st.metric("决策审批", f"{avg_approval:.1f} 天")

# ============================================================
# 第二行 KPI
# ============================================================
st.markdown("---")
col7, col8, col9, col10 = st.columns(4)

with col7:
    st.metric("付款审批", f"{pay_avg:.1f} 天",
              delta="偏快" if pay_avg < 7 and pay_avg > 0 else "偏慢" if pay_avg > 0 else None)
with col8:
    st.metric("最长决策审批", f"{max_approval:.0f} 天" if max_approval > 0 else "无数据")
with col9:
    st.metric("最长付款审批", f"{max_pay:.0f} 天" if max_pay > 0 else "无数据")
with col10:
    st.metric("超7天决策数", f"{over_7} 单")

# ============================================================
# 图表区域：折线图
# ============================================================
st.markdown("---")
st.markdown("## 📈 趋势分析")

col11, col12 = st.columns(2)

with col11:
    inflow_weekly = df_inflow_f.groupby("年月周数")["套数"].sum().reset_index()
    outflow_weekly = df_outflow_f.groupby("年月周数")["套数"].sum().reset_index()

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=inflow_weekly["年月周数"],
        y=inflow_weekly["套数"],
        mode="lines+markers",
        name="决策流入",
        line=dict(color="#2196F3", width=3)
    ))
    fig_trend.add_trace(go.Scatter(
        x=outflow_weekly["年月周数"],
        y=outflow_weekly["套数"],
        mode="lines+markers",
        name="决策流出",
        line=dict(color="#4CAF50", width=3)
    ))
    fig_trend.update_layout(
        title="决策流入 vs 流出趋势",
        xaxis_title="周数",
        yaxis_title="套数",
        height=350,
        hovermode="x unified"
    )
    st.plotly_chart(fig_trend, use_container_width=True)

with col12:
    approval_weekly = df_outflow_f.groupby("年月周数")["决策审批天数"].mean().reset_index()
    pay_approval_weekly = df_payment_out_f.groupby("年月周数")["付款审批天数"].mean().reset_index()

    fig_approval = go.Figure()
    fig_approval.add_trace(go.Scatter(
        x=approval_weekly["年月周数"],
        y=approval_weekly["决策审批天数"],
        mode="lines+markers",
        name="决策审批",
        line=dict(color="#FF9800", width=3)
    ))
    fig_approval.add_trace(go.Scatter(
        x=pay_approval_weekly["年月周数"],
        y=pay_approval_weekly["付款审批天数"],
        mode="lines+markers",
        name="付款审批",
        line=dict(color="#9C27B0", width=3)
    ))
    fig_approval.update_layout(
        title="审批时效趋势",
        xaxis_title="周数",
        yaxis_title="天数",
        height=350,
        hovermode="x unified"
    )
    st.plotly_chart(fig_approval, use_container_width=True)

# ============================================================
# 第三行：柱形图
# ============================================================
st.markdown("---")
st.markdown("## 📊 部门排行")

col13, col14 = st.columns(2)

with col13:
    dept_inflow = df_inflow_f.groupby("所属部门")["套数"].sum().reset_index().sort_values("套数", ascending=False)
    if not dept_inflow.empty:
        fig_dept = px.bar(
            dept_inflow,
            x="所属部门",
            y="套数",
            title="各部门决策流入套数",
            color="套数",
            color_continuous_scale="Blues",
            height=350
        )
        fig_dept.update_layout(showlegend=False)
        st.plotly_chart(fig_dept, use_container_width=True)

with col14:
    dept_pay = df_payment_in_f.groupby("所属部门")["付款金额"].sum().reset_index().sort_values("付款金额",
                                                                                               ascending=False)
    if not dept_pay.empty:
        fig_pay = px.bar(
            dept_pay,
            x="所属部门",
            y="付款金额",
            title="各部门付款金额",
            color="付款金额",
            color_continuous_scale="Greens",
            height=350
        )
        fig_pay.update_layout(showlegend=False)
        st.plotly_chart(fig_pay, use_container_width=True)

# ============================================================
# 第四行：明细表
# ============================================================
st.markdown("---")
st.markdown("## 📋 明细数据")

view_type = st.radio(
    "选择查看明细",
    ["决策流入明细", "决策流出明细", "付款流入明细", "付款流出明细"],
    horizontal=True
)

if view_type == "决策流入明细":
    detail_df = df_inflow_f[["年月周数", "决策编号", "套数", "所属部门", "项目负责人", "提交申请时间"]]
elif view_type == "决策流出明细":
    detail_df = df_outflow_f[["年月周数", "决策编号", "套数", "所属部门", "项目负责人", "审批完成时间", "决策审批天数"]]
elif view_type == "付款流入明细":
    detail_df = df_payment_in_f[
        ["年月周数", "付款编号", "业务编号", "付款金额", "所属部门", "项目负责人", "付款申请时间"]]
else:
    detail_df = df_payment_out_f[
        ["年月周数", "付款编号", "业务编号", "付款金额", "所属部门", "项目负责人", "付款完成时间", "付款审批天数"]]

st.dataframe(detail_df, use_container_width=True, height=400)

# ============================================================
# 底部
# ============================================================
st.markdown("---")
st.caption(f"数据更新时间：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据来源：{'MySQL' if DB_MODE else 'CSV'}")