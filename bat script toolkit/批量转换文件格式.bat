@echo off
setlocal enabledelayedexpansion

for %%f in (*.m4s) do (
    set "input_file=%%f"
    set "output_file=!input_file:.m4s=.mp3!"
    
    echo 正在转换：!input_file!
    ffmpeg -i "!input_file!" -q:a 0 "!output_file!"
)

echo.
echo 所有文件转换完成！
pause