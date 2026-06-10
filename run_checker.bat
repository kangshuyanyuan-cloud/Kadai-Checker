@echo off
chcp 65001 > nul
cd /d "%~dp0"
title Moodle Checker
"C:\Users\Owner\AppData\Local\Programs\Python\Python312\python.exe" "unified_check.py"
