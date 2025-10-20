@echo off
REM 将代码页设置为UTF-8，以正确显示中文文件名
chcp 65001 > nul

REM -----------------------------------------------------------
REM 【PNG无损版】
REM  这个版本会提取无损的PNG格式最后一帧。
REM -----------------------------------------------------------

echo 开始提取最后一帧 (PNG无损版)...
echo.

for %%a in (*.mp4) do (
    echo 正在处理文件: "%%a"
    
    REM -y: 无需确认，直接覆盖旧文件。
    REM -i "%%a": 输入的视频文件。
    REM -update 1: 核心命令。让新帧覆盖旧的输出文件。
    REM "%%~na_lastframe.png": 输出文件名为PNG格式。
    ffmpeg -y -i "%%a" -update 1 "%%~na_lastframe.png"
)

echo.
echo --------------------
echo 所有视频处理完毕！
echo 按任意键退出。
pause > nul