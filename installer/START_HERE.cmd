@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "NEURO_LOG_NAME=NEURO_RT_START_HERE_%RANDOM%_%RANDOM%.log"
set "NEURO_START_LOG=%TEMP%\%NEURO_LOG_NAME%"
if not defined LOCALAPPDATA goto :open_log
set "NEURO_LOG_DIR=%LOCALAPPDATA%\RadioterapiaAI\NEURO_RT\Logs"
if not exist "%NEURO_LOG_DIR%\." mkdir "%NEURO_LOG_DIR%" >nul 2>&1
if exist "%NEURO_LOG_DIR%\." set "NEURO_START_LOG=%NEURO_LOG_DIR%\%NEURO_LOG_NAME%"

:open_log
> "%NEURO_START_LOG%" echo [%DATE% %TIME%] NEURO RT START HERE
if not exist "%NEURO_START_LOG%" set "NEURO_START_LOG="
set "NEURO_WIZARD=%~dp0code\installer\START_HERE.ps1"
set "NEURO_CODE=%~dp0code"
if exist "%NEURO_WIZARD%" (
    if not exist "%~dp0release-manifest.json" goto :incomplete
    goto :verify
)
set "NEURO_WIZARD=%~dp0START_HERE.ps1"
set "NEURO_CODE=%~dp0.."

:verify
if not exist "%NEURO_WIZARD%" goto :incomplete
if not exist "%NEURO_CODE%\neuro_rt\setup_wizard.py" goto :incomplete
if not exist "%NEURO_CODE%\module.json" goto :incomplete

if defined NEURO_START_LOG (
    "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%NEURO_WIZARD%" >> "%NEURO_START_LOG%" 2>&1
) else (
    "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%NEURO_WIZARD%"
)
set "NEURO_RESULT=%ERRORLEVEL%"
if "%NEURO_RESULT%"=="0" exit /b 0
echo O assistente nao abriu ou foi interrompido. Codigo de saida: %NEURO_RESULT%
if defined NEURO_START_LOG >> "%NEURO_START_LOG%" echo Exit code: %NEURO_RESULT%
if defined NEURO_START_LOG type "%NEURO_START_LOG%"
goto :show_log

:incomplete
set "NEURO_RESULT=2"
set "NEURO_MESSAGE=NEURO_SETUP_INCOMPLETE: No Explorador do Windows, clique com o botao direito no ZIP e escolha Extrair Tudo. Abra START_HERE.cmd na pasta extraida."
echo %NEURO_MESSAGE%
if defined NEURO_START_LOG >> "%NEURO_START_LOG%" echo %NEURO_MESSAGE%

:show_log
if defined NEURO_START_LOG echo Diagnostico salvo em "%NEURO_START_LOG%"
pause
exit /b %NEURO_RESULT%
