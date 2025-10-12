@echo off
REM 解决中文乱码：将控制台编码改为 UTF-8 (推荐在Win10/11使用)
chcp 65001 > nul 
setlocal enabledelayedexpansion

REM ******************************************************
REM * 配置选项                                           *
REM ******************************************************

REM 视频文件扩展名列表
set "VIDEO_EXTENSIONS=*.mp4 *.mkv *.avi *.mov *.wmv"

REM FFmpeg 命令参数
REM -vf fps=1 : 设置帧率为 1 帧/秒 (每秒提取一张图片)
REM -q:v 2    : 设置输出图片的质量 (1=最高质量, 31=最低质量), 适用于 JPEG
set "FFMPEG_OPTIONS=-vf fps=1 -q:v 2"

REM ** 关键修改 **
REM 这里只定义 FFmpeg 序列所需的双百分号转义模式。
REM **注意：** 在 FOR 循环外定义时，FFmpeg 的 % 序列模式只需 **双写 (%%)**。
set "IMAGE_SEQUENCE_PATTERN=%%04d.jpg"

REM ******************************************************
REM * 循环处理视频文件                                   *
*********************************************************

echo ----------------------------------------
echo 开始提取视频帧...
echo ----------------------------------------

FOR %%F IN (%VIDEO_EXTENSIONS%) DO (
    REM FOR 循环变量 %%F: 完整文件名 (带扩展名)
    REM FOR 循环变量 %%~nF: 文件名 (不带扩展名)，用作文件夹名和图片前缀

    set "INPUT_FILE=%%F"
    set "OUTPUT_DIR=%%~nF"

    echo.
    echo 正在处理文件: "!INPUT_FILE!"
    
    REM 检查输出文件夹是否存在，如果不存在则创建
    if not exist "!OUTPUT_DIR!" (
        mkdir "!OUTPUT_DIR!"
        echo 已创建输出文件夹: "!OUTPUT_DIR!"
    )

    REM ** 核心修正：将 %%~nF 直接写入命令中，并将序列模式变量扩展 **
    REM 完整输出路径示例: "视频文件名\视频文件名_0001.jpg"
    ffmpeg -i "!INPUT_FILE!" !FFMPEG_OPTIONS! "%%~nF\%%~nF_!IMAGE_SEQUENCE_PATTERN!"
    
    REM 检查 FFmpeg 命令的返回代码
    if errorlevel 1 (
        echo 警告: FFmpeg 处理 "!INPUT_FILE!" 失败。
    ) else (
        echo 成功提取帧到文件夹: "!OUTPUT_DIR!"
    )
)

echo.
echo ----------------------------------------
echo 所有视频文件处理完成。
echo ----------------------------------------

pause
endlocal
