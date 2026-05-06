@echo off
chcp 65001 >nul
echo 画像ギャラリーデータを生成中...
python "%~dp0generate_gallery_data.py"
echo.
pause
