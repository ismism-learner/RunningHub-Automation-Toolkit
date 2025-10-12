@echo off
setlocal enabledelayedexpansion

REM =================================================================
REM FFMpeg 视频切分脚本 (以 10 秒为时长)
REM 
REM **重要说明：**
REM 1. 确保已安装 FFmpeg，并且 'ffmpeg' 命令可以在命令行中直接运行（即已添加到系统路径）。
REM 2. 将此脚本放在包含你要切割的视频文件的文件夹中。
REM 3. 切割后的文件将保存在当前文件夹下的 '_output_10s' 子文件夹中。
REM 4. 使用 `-c copy` 选项，切割速度快，但切割点可能不精确到毫秒，
REM    它会寻找最近的关键帧（Keyframe）作为起点。
REM =================================================================

REM 设置切分时长为 10 秒
set SEGMENT_TIME=10

REM 设置输出文件夹名称
set OUTPUT_DIR=_output_10s

REM 创建输出文件夹
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo.
echo ----------------------------------------------------
echo 正在开始视频切分，每段时长 %SEGMENT_TIME% 秒。
echo 输出文件夹: %OUTPUT_DIR%
echo ----------------------------------------------------
echo.

REM 遍历当前文件夹下的所有常见视频文件（你可以根据需要添加或删除扩展名）
for %%f in (*.mp4 *.mkv *.avi *.mov *.wmv) do (
    
    echo ----------------------------------------------------
    echo 正在处理文件: "%%f"
    
    REM 获取文件名（不含扩展名）
    set "FILE_NAME_NO_EXT=%%~nf"
    REM 获取文件扩展名
    set "FILE_EXT=%%~xf"

    REM 构建输出文件名格式: 原始文件名_段号.扩展名 (例如: myvideo_001.mp4)
    REM 注意: %%03d 会生成 3 位数字的段号 (000, 001, 002...)
    set "OUTPUT_FORMAT=!FILE_NAME_NO_EXT!_%%03d!FILE_EXT!"
    
    REM FFmpeg 切割命令
    REM -i "%%f"                 : 输入文件
    REM -c copy                 : 复制流，不重新编码 (速度快)
    REM -map 0                  : 复制所有流 (视频、音频等)
    REM -f segment              : 使用 segment 格式
    REM -segment_time %SEGMENT_TIME% : 设置每个段的时长 (秒)
    REM -reset_timestamps 1     : 重置每个段的时间戳
    REM "%OUTPUT_DIR%\!OUTPUT_FORMAT!" : 输出文件路径和格式
    
    ffmpeg -i "%%f" -c copy -map 0 -f segment -segment_time %SEGMENT_TIME% -reset_timestamps 1 "%OUTPUT_DIR%\!OUTPUT_FORMAT!"
    
    echo 文件 "%%f" 处理完成。
    echo ----------------------------------------------------
    echo.
)

echo.
echo ====================================================
echo 所有视频切分完成！
echo ====================================================

pause
