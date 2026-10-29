@echo off
setlocal
cd /d "%~dp0"
if not exist "runtime" mkdir "runtime"
set "NEURO_PY=%~dp0python\python.exe"
if not exist "%NEURO_PY%" set "NEURO_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%NEURO_PY%" (
  echo Runtime nao preparado. Execute PREPARAR.cmd primeiro.
  pause
  exit /b 1
)
echo NeuroRT: http://127.0.0.1:8766/neuro/
echo Creditos e licencas: NOTICE e docs\INSTALACAO_E_CREDITOS.md
echo Log: %~dp0runtime\server.log
set "PYTHONUTF8=1"
"%NEURO_PY%" -u -m neuro_rt.server >> "%~dp0runtime\server.log" 2>&1
if errorlevel 1 type "%~dp0runtime\server.log"
pause
