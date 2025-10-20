@echo off
SETLOCAL

REM --- 您可以自定义这里的配置 ---
REM 设置要匹配的文件名模式 (例如 *.mp4, video_part_*.mkv 等)
SET file_pattern=*.mp4

REM 设置最终输出的文件名
SET output_filename=merged_by_time_output.mp4

REM 设置用于合并的临时列表文件名
SET list_filename=mergelist.txt
REM --------------------------------

ECHO Preparing to merge video files...

REM 1. 如果旧的列表文件存在，先删除它，以防重复运行出错
IF EXIST "%list_filename%" DEL "%list_filename%"

ECHO.
ECHO Creating a list of files to merge in order of modification time (oldest first)...
REM 2. **核心修改**: 使用 dir 命令按修改日期排序(/o:d)来生成文件列表
(FOR /F "tokens=*" %%F IN ('dir /b /o:d "%file_pattern%"') DO (
    ECHO file '%%F'
)) > "%list_filename%"

ECHO The following files will be merged in this order:
ECHO -------------------------------------------------
type "%list_filename%"
ECHO -------------------------------------------------
ECHO.

ECHO Starting FFmpeg to merge files...
REM 3. 调用 ffmpeg 使用 concat demuxer 进行合并 (-c copy 实现无损快速合并)
ffmpeg -f concat -safe 0 -i "%list_filename%" -c copy "%output_filename%"

ECHO.
ECHO Merging complete. Cleaning up temporary files...
REM 4. 删除临时的列表文件
DEL "%list_filename%"

ECHO.
ECHO Done! The merged video is saved as "%output_filename%".
pause
ENDLOCAL