@echo off
rem Arranca el servidor de Recibo BOS y abre la aplicacion.
cd /d "%~dp0"

rem 127.0.0.1 = solo este PC. Para que otros equipos del CEDI entren, cambie a 0.0.0.0
rem y pida a TI abrir el puerto en el firewall de Windows.
set "HOST=127.0.0.1"
set "PUERTO=8080"

rem Si el servidor ya esta corriendo, solo se abre la ventana de la aplicacion.
powershell -NoProfile -Command "try { (New-Object Net.Sockets.TcpClient('127.0.0.1', %PUERTO%)).Close(); exit 0 } catch { exit 1 }"
if %errorlevel%==0 goto abrir

start "Recibo BOS - servidor (no cerrar)" /min venv\Scripts\python.exe -m waitress --listen=%HOST%:%PUERTO% app:app
timeout /t 3 /nobreak >nul

:abrir
rem --kiosk-printing imprime directo en la impresora predeterminada, sin mostrar el cuadro de impresion.
start "" msedge --app=http://127.0.0.1:%PUERTO%/recibo --kiosk-printing --user-data-dir="%LOCALAPPDATA%\ReciboBOS\navegador"
