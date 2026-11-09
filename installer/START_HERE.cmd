@echo off
setlocal
set "NEURO_WIZARD=%~dp0code\installer\START_HERE.ps1"
if not exist "%NEURO_WIZARD%" set "NEURO_WIZARD=%~dp0START_HERE.ps1"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%NEURO_WIZARD%"
set "NEURO_RESULT=%ERRORLEVEL%"
if not "%NEURO_RESULT%"=="0" pause
exit /b %NEURO_RESULT%
