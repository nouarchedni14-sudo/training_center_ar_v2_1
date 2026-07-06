@echo off
cd /d %~dp0
python reorganize_media.py --move
pause