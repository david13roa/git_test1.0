@echo off
REM ============================================================
REM  Informe de diferencias de despacho por picker
REM  Doble clic para ejecutar, o arrastre el Excel sobre este
REM  archivo para procesar ese archivo en particular.
REM ============================================================
setlocal
cd /d "%~dp0"
chcp 65001 >nul

echo ============================================================
echo  INFORME DE DIFERENCIAS DE DESPACHO
echo ============================================================
echo.

REM --- Buscar Python en el equipo ---
set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY (where python >nul 2>&1 && set "PY=python")

if not defined PY (
    echo ERROR: no se encontro Python en este equipo.
    echo.
    echo Instalelo desde https://www.python.org/downloads/
    echo IMPORTANTE: marque la casilla "Add Python to PATH" al instalar.
    echo.
    pause
    exit /b 1
)

REM --- Instalar las librerias necesarias la primera vez ---
%PY% -c "import pandas, openpyxl" >nul 2>&1
if errorlevel 1 (
    echo Instalando librerias necesarias, espere un momento...
    echo.
    %PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo.
        echo No se pudieron instalar las librerias automaticamente.
        echo Puede ser el proxy o los permisos de la red de la empresa.
        echo Intente ejecutar en una consola:
        echo     %PY% -m pip install --user pandas openpyxl
        echo.
        pause
        exit /b 1
    )
    echo Librerias instaladas correctamente.
    echo.
)

REM --- Ejecutar (si se arrastro un archivo, se usa ese) ---
if "%~1"=="" (
    %PY% informe_diferencias.py
) else (
    %PY% informe_diferencias.py "%~1"
)

echo.
pause
