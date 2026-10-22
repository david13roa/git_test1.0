"""Configuración de la impresora de Windows desde la aplicación.

Edge imprime los rótulos con --kiosk-printing (sin cuadro de impresión), así que la doble cara,
el color y el ahorro de tóner salen de dos lugares:
  1. Las preferencias del controlador de la impresora en Windows (EcoPrint, dúplex).
  2. Los ajustes que Edge recuerda de la última impresión en su perfil ("sticky settings").
Este módulo permite revisar y corregir ambos sin entrar al Panel de control.

Uso desde iniciar.bat, antes de abrir Edge:
    python impresora.py navegador "%LOCALAPPDATA%\\ReciboBOS\\navegador"
"""
import json
import os
import subprocess
import sys

ES_WINDOWS = os.name == "nt"
_SIN_VENTANA = 0x08000000 if ES_WINDOWS else 0  # CREATE_NO_WINDOW

_PS_LISTAR = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$lista = foreach ($p in Get-CimInstance Win32_Printer) {
  $duplex = $null; $color = $null
  try {
    $cfg = Get-PrintConfiguration -PrinterName $p.Name -ErrorAction Stop
    $duplex = "$($cfg.DuplexingMode)"; $color = [bool]$cfg.Color
  } catch {}
  [pscustomobject]@{ nombre = $p.Name; predeterminada = [bool]$p.Default; duplex = $duplex; color = $color }
}
ConvertTo-Json -Compress -InputObject @($lista)
"""

# "Dejar que Windows administre la impresora predeterminada" cambia la predeterminada sola: se desactiva.
_PS_PREDETERMINAR = r"""
Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Windows' -Name LegacyDefaultPrinterMode -Value 1
(New-Object -ComObject WScript.Network).SetDefaultPrinter($env:RB_IMPRESORA)
"""

_PS_UNA_CARA = r"""
Set-PrintConfiguration -PrinterName $env:RB_IMPRESORA -DuplexingMode OneSided -Color $false -ErrorAction Stop
"""


class ErrorImpresora(Exception):
    pass


def _powershell(script, impresora=None, espera=30):
    if not ES_WINDOWS:
        raise ErrorImpresora("Solo disponible en el PC con Windows")
    # El nombre de la impresora va por variable de entorno para no armar comandos con texto del usuario.
    entorno = dict(os.environ, RB_IMPRESORA=impresora or "")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                           capture_output=True, timeout=espera, env=entorno, creationflags=_SIN_VENTANA)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ErrorImpresora(f"No se pudo consultar Windows: {e}")
    salida = r.stdout.decode("utf-8-sig", errors="replace").strip()
    if r.returncode != 0:
        error = r.stderr.decode("utf-8", errors="replace").strip().splitlines()
        raise ErrorImpresora(error[0] if error else "Windows rechazó el cambio")
    return salida


def listar():
    """Impresoras instaladas: [{nombre, predeterminada, duplex, color}]. duplex: OneSided, TwoSidedLongEdge…"""
    salida = _powershell(_PS_LISTAR)
    return [p for p in json.loads(salida) if p] if salida else []


def _validar(nombre):
    if nombre not in {p["nombre"] for p in listar()}:
        raise ErrorImpresora("Esa impresora no está instalada en este PC")


def predeterminar(nombre):
    _validar(nombre)
    _powershell(_PS_PREDETERMINAR, nombre)


def una_cara(nombre):
    """Deja la impresora en una cara y blanco y negro como valor por defecto del controlador."""
    _validar(nombre)
    try:
        _powershell(_PS_UNA_CARA, nombre)
    except ErrorImpresora as e:
        raise ErrorImpresora(f"Windows no dejó cambiarlo ({e}). Use «Abrir preferencias» y elija "
                             "impresión a una cara.")


def abrir_preferencias(nombre):
    """Abre la ventana "Preferencias de impresión" del controlador (ahí está EcoPrint de Kyocera)."""
    _validar(nombre)
    subprocess.Popen(f'rundll32 printui.dll,PrintUIEntry /e /n "{nombre}"')


# ---------------------------------------------------------------- perfil de Edge

# Valores que Edge toma al imprimir sin cuadro: una cara, blanco y negro, sin encabezado ni pie
# (la URL y la fecha también gastan tóner) y márgenes del rótulo. Sin destinos recientes,
# Edge imprime en la impresora predeterminada de Windows.
AJUSTES_EDGE = {
    "isDuplexEnabled": False,
    "isDuplexShortEdge": False,
    "isColorEnabled": False,
    "isHeaderFooterEnabled": False,
    "isCssBackgroundEnabled": True,
    "isLandscapeEnabled": True,
    "marginsType": 0,
    "scaling": "100",
}


def ajustar_navegador(carpeta_perfil):
    """Fija los ajustes de impresión que Edge recuerda en el perfil de la app.

    Debe correr con la ventana de Recibo BOS cerrada: Edge reescribe el archivo al salir.
    """
    ruta = os.path.join(carpeta_perfil, "Default", "Preferences")
    preferencias = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                preferencias = json.load(f)
        except (OSError, ValueError):
            return False  # archivo en uso o dañado: no se toca
    pegajosos = preferencias.setdefault("printing", {}).setdefault("print_preview_sticky_settings", {})
    try:
        estado = json.loads(pegajosos.get("appState") or "{}")
    except ValueError:
        estado = {}
    estado.setdefault("version", 2)
    estado.update(AJUSTES_EDGE)
    estado["recentDestinations"] = []
    pegajosos["appState"] = json.dumps(estado)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    temporal = ruta + ".recibo-bos"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(preferencias, f)
    os.replace(temporal, ruta)
    return True


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "navegador":
        ajustar_navegador(sys.argv[2])
    else:
        print(__doc__)
