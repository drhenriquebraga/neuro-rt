@echo off
setlocal
cd /d "%~dp0"
echo NeuroRT usa pesos publicos de terceiros. Origem e licencas:
type NOTICE
if not exist "runtime" mkdir "runtime"
set "PYTHONUTF8=1"
if not exist "python\python.exe" (
  python scripts\build_portable_runtime.py > runtime\prepare.log 2>&1
  if errorlevel 1 goto erro
)
python\python.exe scripts\prepare_models.py --models all >> runtime\prepare.log 2>&1
if errorlevel 1 goto erro
python\python.exe -c "import raidionicsseg.fit,SimpleITK,nibabel,pydicom,onnxruntime" >> runtime\prepare.log 2>&1
if errorlevel 1 goto erro
echo NeuroRT preparado. Execute INICIAR.cmd.
pause
exit /b 0
:erro
type runtime\prepare.log
echo Falha no preparo. O log foi preservado.
pause
exit /b 1
