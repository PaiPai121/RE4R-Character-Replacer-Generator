@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Replacer.ps1" -Configure
if errorlevel 1 pause
