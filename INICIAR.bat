@echo off
rem =====================================================================
rem  Titicaca Vivo - doble clic para arrancar (Windows)
rem   1. Busca el entorno virtual del proyecto (INSTRUCCIONES.txt, PASO 2).
rem   2. Ejecuta servidor.py: revisa .env, MySQL y la base antes de abrir
rem      el puerto, y si algo falta dice exactamente que hacer.
rem   3. Abre el navegador en http://127.0.0.1:8080
rem  Para detenerlo: Ctrl + C en esta ventana (o cerrarla).
rem  Extra: INICIAR.bat --host 0.0.0.0   (para abrirla desde un celular)
rem =====================================================================
title Titicaca Vivo
cd /d "%~dp0"

set "PY=%USERPROFILE%\.venvs\titicaca_vivo\Scripts\python.exe"
if exist "%PY%" goto arrancar
set "PY=%~dp0.venv\Scripts\python.exe"
if exist "%PY%" goto arrancar
set "PY=%~dp0venv\Scripts\python.exe"
if exist "%PY%" goto arrancar

echo.
echo  [X]  No encuentro el entorno virtual de Titicaca Vivo.
echo       Se crea UNA sola vez. En PowerShell, dentro de esta carpeta:
echo.
echo         py -3.13 -m venv $env:USERPROFILE\.venvs\titicaca_vivo
echo         ^& $env:USERPROFILE\.venvs\titicaca_vivo\Scripts\Activate.ps1
echo         pip install -r requirements.txt
echo.
echo       Despues vuelve a hacer doble clic en INICIAR.bat
echo       El paso a paso completo esta en INSTRUCCIONES.txt, PASO 2.
echo.
pause
exit /b 1

:arrancar
"%PY%" servidor.py --abrir %*
echo.
pause
