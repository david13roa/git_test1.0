@echo off
rem Instala Recibo BOS en este PC (solo se ejecuta una vez).
cd /d "%~dp0"
title Instalar Recibo BOS

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY goto sinpython

if exist venv\Scripts\python.exe goto dependencias
echo [1/4] Creando el entorno de Python...
%PY% -m venv venv || goto error

:dependencias
echo [2/4] Instalando librerias (necesita internet)...
venv\Scripts\python.exe -m pip install --quiet --upgrade pip
venv\Scripts\python.exe -m pip install --quiet -r requirements.txt || goto error

echo [3/4] Preparando la base de datos...
if exist datos\recibo_bos.db goto acceso
set "EXCEL="
for %%f in (*.xlsm) do set "EXCEL=%%f"
if not defined EXCEL goto sinexcel
echo        Importando portafolio, personal y consolidado de "%EXCEL%"
venv\Scripts\python.exe importar_excel.py "%EXCEL%" --historico || goto error
goto acceso

:sinexcel
echo        No hay un archivo .xlsm en esta carpeta: la base queda vacia.
echo        Puede cargar el portafolio despues desde la pantalla Portafolio.
venv\Scripts\python.exe -c "import db; db.inicializar()" || goto error

:acceso
echo [4/4] Creando el acceso directo "Recibo BOS" en el escritorio...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Recibo BOS.lnk'); $s.TargetPath='%~dp0iniciar.bat'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.Save()"

echo.
echo Listo. Abra Recibo BOS con el acceso directo del escritorio.
pause
exit /b 0

:sinpython
echo No se encontro Python.
echo Instalelo desde https://www.python.org/downloads/ y vuelva a ejecutar este archivo.
pause
exit /b 1

:error
echo.
echo Ocurrio un error durante la instalacion. Revise los mensajes de arriba.
pause
exit /b 1
