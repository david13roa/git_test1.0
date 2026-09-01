@echo off
REM ============================================================
REM  Servidor del tablero de diferencias de cava
REM  Doble clic para levantarlo. Deje esta ventana abierta.
REM ============================================================
setlocal
cd /d "%~dp0"
chcp 65001 >nul

echo ============================================================
echo  SERVIDOR - CONTROL DE DIFERENCIAS DE CAVA
echo ============================================================
echo.

set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY (where python >nul 2>&1 && set "PY=python")

if not defined PY (
    echo ERROR: no se encontro Python en este equipo.
    echo Instalelo desde https://www.python.org/downloads/
    echo IMPORTANTE: marque "Add Python to PATH" al instalar.
    echo.
    pause
    exit /b 1
)

%PY% -c "import fastapi, uvicorn, pandas, openpyxl" >nul 2>&1
if errorlevel 1 (
    echo Instalando librerias necesarias, espere un momento...
    echo.
    %PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo.
        echo No se pudieron instalar las librerias.
        echo Puede ser el proxy de la red. Intente en una consola:
        echo     %PY% -m pip install --user fastapi "uvicorn[standard]" python-multipart pandas openpyxl
        echo.
        pause
        exit /b 1
    )
)

if not exist "datos\activo.xlsx" (
    echo AVISO: no hay ningun Excel cargado todavia.
    echo Copie el archivo de diferencias como datos\activo.xlsx,
    echo o subalo despues desde http://localhost:8000/docs
    echo.
)

echo Abriendo el tablero en http://localhost:8000
echo Documentacion de la API en http://localhost:8000/docs
echo.
echo Para detener el servidor cierre esta ventana o presione Ctrl+C.
echo.

start "" http://localhost:8000
%PY% -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

pause
