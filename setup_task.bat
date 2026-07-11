@echo off
REM ============================================
REM Dashboard 数据同步 - 定时任务安装
REM ============================================
REM 双击运行即可创建定时任务
REM 默认每小时执行一次
REM
REM 数据源: C:\Users\hc\Desktop\决策+付款\ 目录下最新的 .xlsx
REM 脚本会自动检测最新 Excel 文件并同步到 GitHub
REM
REM 删除任务: schtasks /delete /tn "DashboardDataSync" /f
REM ============================================

echo.
echo === 创建 Dashboard 数据同步定时任务 ===
echo.

REM ---- 配置区 ----
REM Python 路径（项目 venv 里的 python）
set PYTHON_PATH=D:\pycharm\.venv\Scripts\python.exe

REM 项目目录
set PROJECT_DIR=D:\pycharm

REM 执行频率
REM /sc hourly       = 每小时
REM /sc daily /st 08:00 = 每天早8点
REM /sc hourly /mo 2    = 每2小时
REM /sc minute /mo 30   = 每30分钟
set SCHEDULE=/sc hourly
REM ---- 配置区结束 ----

echo Python:   %PYTHON_PATH%
echo 项目目录: %PROJECT_DIR%
echo 数据源:   桌面\决策+付款\ 最新 Excel (自动检测)
echo 频率:     每小时
echo.

REM 创建任务（调用 sync_from_excel.py，自动检测桌面最新 Excel）
schtasks /create /tn "DashboardDataSync" /tr "%PYTHON_PATH% %PROJECT_DIR%\sync_from_excel.py" %SCHEDULE% /f

if %errorlevel% equ 0 (
    echo.
    echo [OK] 定时任务创建成功！
    echo.
    echo 任务名: DashboardDataSync
    echo 频率:   每小时自动执行
    echo 流程:   读取桌面Excel -> 生成CSV -> 推送GitHub -> Streamlit自动更新
    echo.
    echo 查看任务: schtasks /query /tn "DashboardDataSync"
    echo 手动执行: schtasks /run /tn "DashboardDataSync"
    echo 删除任务: schtasks /delete /tn "DashboardDataSync" /f
) else (
    echo.
    echo [FAIL] 创建失败，请以管理员身份运行
)

echo.
pause
