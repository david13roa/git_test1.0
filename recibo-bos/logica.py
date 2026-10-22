"""Reglas de negocio del recibo, equivalentes a las fórmulas de la hoja
"ROTULO RECIBO FEFO-FIFO" del Excel original."""
from datetime import date

PREFIJO_MATERIAL = 12000000  # En el Excel: B17 = 12000000 + E3


def normalizar_codigo(texto):
    """Devuelve ("material", n) o ("ean", texto) según lo que se digitó o escaneó.

    - Hasta 7 dígitos: últimos dígitos del material (igual que el Excel).
    - 8 dígitos: material completo.
    - 9 o más dígitos: código de barras EAN de la caja.
    """
    t = (texto or "").strip()
    if not t.isdigit():
        return None
    if len(t) <= 7:
        return ("material", PREFIJO_MATERIAL + int(t))
    if len(t) == 8:
        return ("material", int(t))
    return ("ean", t)


def codigo_corto(material):
    """Últimos 4 dígitos que se imprimen en grande en el rótulo: 12000444 -> "0444"."""
    return str(material)[-4:]


def calcular(cantidad, cajas_estiba, vencimiento, vida_min, hoy=None):
    """Cálculos del rótulo.

    cajas_estiba: patrón de estibado digitado o, si no hay, el del portafolio (M4).
    """
    hoy = hoy or date.today()
    completas = cantidad // cajas_estiba                      # K4
    saldo = cantidad - completas * cajas_estiba               # M8
    dias_vida = (vencimiento - hoy).days if vencimiento else None  # H4
    if not vida_min:
        status = "SIN DATO"                                   # I4 "---" / "AGREGAR"
    elif dias_vida is None:
        status = ""
    elif dias_vida < vida_min:
        status = "NO CUMPLE"
    else:
        status = "CUMPLE"
    return {
        "estibas_completas": completas,
        "saldo": saldo,
        "estiba_saldo": 1 if saldo >= 1 else 0,               # K8
        "total_estibas": completas + (1 if saldo >= 1 else 0),
        "dias_vida": dias_vida,
        "status": status,
    }


def texto_qr(material, cajas, vencimiento):
    """Contenido del QR que lee la app de Power Apps del montacarguista.

    Debe quedar idéntico al Excel: =CONCAT(B17,"/",B18,"/",TEXT(E7,"dd-mm-yyyy"))
    Ej.: 12005445/100/02-12-2026
    """
    return f"{material}/{cajas}/{vencimiento.strftime('%d-%m-%Y')}"


def estibas_del_recibo(recibo):
    """Lista de rótulos a imprimir: uno por estiba completa y uno por el saldo."""
    total = recibo["estibas_completas"] + (1 if recibo["saldo"] >= 1 else 0)
    estibas = []
    for i in range(recibo["estibas_completas"]):
        estibas.append({"numero": i + 1, "total": total, "cajas": recibo["cajas_estiba"], "es_saldo": False})
    if recibo["saldo"] >= 1:
        estibas.append({"numero": total, "total": total, "cajas": recibo["saldo"], "es_saldo": True})
    return estibas


def a_entero(valor):
    """Convierte valores del portafolio como 150, "150", "150CEDI" o "" a entero o None."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return int(valor)
    digitos = "".join(c for c in str(valor) if c.isdigit())
    return int(digitos) if digitos else None
