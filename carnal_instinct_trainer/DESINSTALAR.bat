@echo off
title Desinstalar CITrainer
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1" -Uninstall
pause
