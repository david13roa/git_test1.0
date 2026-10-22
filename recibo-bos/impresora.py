"""Configuración de la impresora de Windows desde la aplicación.

Edge imprime los rótulos con --kiosk-printing (sin cuadro de impresión), así que la doble cara,
el color y el ahorro de tóner salen de dos lugares:
  1. Las preferencias del controlador de la impresora en Windows (EcoPrint, dúplex).
  2. Los ajustes que Edge recuerda de la última impresión en su perfil ("sticky settings").
Este módulo permite revisar y corregir ambos sin entrar al Panel de control.

Como Edge puede seguir imprimiendo a doble cara aunque se corrijan ambos, la "impresión directa"
no usa el cuadro de impresión de Edge: convierte el rótulo en PDF con Edge sin ventana y lo manda
a la impresora predeterminada desde Python, pidiéndole al controlador una cara en cada trabajo.

Uso desde iniciar.bat, antes de abrir Edge (también deja de predeterminada una impresora de papel):
    python impresora.py navegador "%LOCALAPPDATA%\\ReciboBOS\\navegador"
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

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


# ---------------------------------------------------------------- impresión directa

DPI = 300
RUTAS_EDGE = [
    os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), r"Microsoft\Edge\Application\msedge.exe"),
    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), r"Microsoft\Edge\Application\msedge.exe"),
]

# Constantes de Windows (wingdi.h)
DM_ORIENTATION, DM_PAPERSIZE, DM_COLOR, DM_DUPLEX = 0x1, 0x2, 0x800, 0x1000
DMORIENT_LANDSCAPE, DMPAPER_LETTER, DMCOLOR_MONOCHROME, DMDUP_SIMPLEX = 2, 1, 1, 1
DM_OUT_BUFFER, DM_IN_BUFFER = 2, 8
PHYSICALWIDTH, PHYSICALHEIGHT, PHYSICALOFFSETX, PHYSICALOFFSETY = 110, 111, 112, 113


# Impresoras que no imprimen en papel: con ellas Windows abre el cuadro "Guardar como".
VIRTUALES = ("pdf", "xps", "onenote", "fax", "send to", "enviar a")


def es_virtual(nombre):
    return any(v in nombre.lower() for v in VIRTUALES)


def elegir(nombres, predeterminada=None, configurada=None):
    """Impresora para los rótulos: la elegida en la app; si no, la predeterminada si es de papel;
    si no, la primera Kyocera o la primera de papel. None si solo hay impresoras virtuales."""
    if configurada in nombres:
        return configurada
    fisicas = [n for n in nombres if not es_virtual(n)]
    if predeterminada in fisicas:
        return predeterminada
    kyocera = [n for n in fisicas if "kyocera" in n.lower()]
    return (kyocera or fisicas or [None])[0]


def directa_disponible():
    """La impresión directa necesita Windows, Edge y las librerías que instala instalar.bat."""
    if not ES_WINDOWS:
        return False
    try:
        import pypdfium2, win32print, win32ui  # noqa: F401
    except ImportError:
        return False
    return _ruta_edge() is not None


def _ruta_edge():
    for ruta in RUTAS_EDGE:
        if os.path.exists(ruta):
            return ruta
    return shutil.which("msedge")


def pagina_a_pdf(url, destino, navegador=None):
    """Guarda la página del rótulo como PDF con Edge sin ventana (respeta @page: carta horizontal)."""
    navegador = navegador or _ruta_edge()
    if not navegador:
        raise ErrorImpresora("No se encontró Microsoft Edge")
    # Perfil aparte: con el de la app abierto, Edge le pasaría la orden a esa ventana en vez de hacer el PDF.
    perfil = os.path.join(tempfile.gettempdir(), "ReciboBOS-pdf")
    try:
        subprocess.run([navegador, "--headless", "--disable-gpu", "--no-first-run", f"--user-data-dir={perfil}",
                        "--no-pdf-header-footer", "--print-to-pdf-no-header", f"--print-to-pdf={destino}", url],
                       capture_output=True, timeout=60, creationflags=_SIN_VENTANA)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ErrorImpresora(f"Edge no pudo preparar el rótulo: {e}")
    if not os.path.exists(destino) or os.path.getsize(destino) == 0:
        raise ErrorImpresora("Edge no pudo preparar el rótulo en PDF")


def paginas_pdf(ruta_pdf, dpi=DPI):
    """Cada hoja del PDF como imagen en escala de grises (la impresora la pasa a puntos, como el gris del modo eco)."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(ruta_pdf)
    try:
        for pagina in pdf:
            yield pagina.render(scale=dpi / 72, grayscale=True).to_pil().convert("RGB")
    finally:
        pdf.close()


def _modo_una_cara(win32print, manejador, nombre):
    """Preferencias de la impresora (con EcoPrint si se activó) + una cara, horizontal, carta y B/N."""
    modo = None
    for nivel in (9, 2):  # 9 = preferencias del usuario, 2 = de la impresora
        try:
            modo = win32print.GetPrinter(manejador, nivel)["pDevMode"]
        except Exception:
            modo = None
        if modo is not None:
            break
    if modo is None:
        raise ErrorImpresora("Windows no entregó la configuración de la impresora")
    modo.Duplex = DMDUP_SIMPLEX
    modo.Orientation = DMORIENT_LANDSCAPE
    modo.PaperSize = DMPAPER_LETTER
    modo.Color = DMCOLOR_MONOCHROME
    modo.Fields |= DM_DUPLEX | DM_ORIENTATION | DM_PAPERSIZE | DM_COLOR
    # El controlador valida y completa los cambios (su parte privada conserva EcoPrint).
    win32print.DocumentProperties(0, manejador, nombre, modo, modo, DM_IN_BUFFER | DM_OUT_BUFFER)
    return modo


def imprimir_pdf(ruta_pdf, configurada=None, titulo="Rótulo Recibo BOS"):
    """Imprime el PDF en la impresora de los rótulos, una hoja por página y a una sola cara."""
    try:
        import win32gui, win32print, win32ui
        from PIL import ImageWin
    except ImportError:
        raise ErrorImpresora("Faltan librerías para imprimir directo: ejecute instalar.bat otra vez")
    nombres = [p["pPrinterName"] for p in win32print.EnumPrinters(
        win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS, None, 4)]
    try:
        predeterminada = win32print.GetDefaultPrinter()
    except Exception:  # Windows sin impresora predeterminada
        predeterminada = None
    nombre = elegir(nombres, predeterminada, configurada)
    if not nombre:
        raise ErrorImpresora("No hay ninguna impresora de papel instalada (solo PDF o similares)")
    if es_virtual(nombre):
        raise ErrorImpresora(f"«{nombre}» guarda archivos en vez de imprimir: elija la Kyocera en la pestaña Impresora")
    manejador = win32print.OpenPrinter(nombre)
    try:
        modo = _modo_una_cara(win32print, manejador, nombre)
    finally:
        win32print.ClosePrinter(manejador)
    dc = win32ui.CreateDCFromHandle(win32gui.CreateDC("WINSPOOL", nombre, modo))
    try:
        # La hoja completa cubre también el borde que la impresora no alcanza a imprimir: así no se encoge.
        ancho, alto = dc.GetDeviceCaps(PHYSICALWIDTH), dc.GetDeviceCaps(PHYSICALHEIGHT)
        dx, dy = dc.GetDeviceCaps(PHYSICALOFFSETX), dc.GetDeviceCaps(PHYSICALOFFSETY)
        dc.StartDoc(titulo)
        try:
            for imagen in paginas_pdf(ruta_pdf):
                if (imagen.width > imagen.height) != (ancho > alto):
                    imagen = imagen.rotate(90, expand=True)  # el controlador ignoró la orientación
                dc.StartPage()
                ImageWin.Dib(imagen).draw(dc.GetHandleOutput(), (-dx, -dy, ancho - dx, alto - dy))
                dc.EndPage()
            dc.EndDoc()
        except Exception:
            dc.AbortDoc()
            raise
    finally:
        dc.DeleteDC()
    return nombre


def imprimir_url(url, configurada=None):
    """Rótulo (URL de la app) -> PDF -> impresora de los rótulos a una cara. Devuelve el nombre de la impresora."""
    carpeta = tempfile.mkdtemp(prefix="recibo-bos-")
    try:
        ruta = os.path.join(carpeta, "rotulo.pdf")
        pagina_a_pdf(url, ruta)
        return imprimir_pdf(ruta, configurada)
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)


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


def corregir_predeterminada(configurada=None):
    """Si la predeterminada de Windows guarda archivos (PDF, OneNote…), Edge pediría "Guardar como":
    se cambia por la impresora de los rótulos."""
    impresoras = listar()
    actual = next((p["nombre"] for p in impresoras if p["predeterminada"]), None)
    nombre = elegir([p["nombre"] for p in impresoras], actual, configurada)
    if nombre and nombre != actual and (actual is None or es_virtual(actual) or configurada == nombre):
        predeterminar(nombre)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "navegador":
        ajustar_navegador(sys.argv[2])
        try:
            import db
            corregir_predeterminada(db.leer_config("impresora_rotulos"))
        except Exception as e:  # sin esto la app igual abre
            print(f"No se pudo revisar la impresora predeterminada: {e}")
    else:
        print(__doc__)
