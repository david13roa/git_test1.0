#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arma el tablero web: mete el JSON de datos dentro de la plantilla HTML.

El resultado es UN SOLO archivo .html que funciona sin servidor, sin internet
y sin instalar nada: se abre con doble clic o se publica en cualquier sitio web.

Uso:
    python preparar_datos_web.py INFORME_DIFERENCIAS.xlsx -o datos.json
    python tablero/construir.py datos.json -o tablero_diferencias.html

O en un solo paso:
    python tablero/construir.py --excel INFORME_DIFERENCIAS.xlsx
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
MARCA = "/*__DATOS__*/"
MARCA_EXCLUSIONES = "/*__EXCLUSIONES__*/"
MARCA_LECTOR = "/*__LECTOR__*/"
LECTOR = RAIZ / "vendor" / "xlsx.full.min.js"
EXCLUSIONES = RAIZ.parent / "exclusiones.json"


def construir(datos: str, plantilla: Path, salida: Path) -> None:
    html = plantilla.read_text(encoding="utf-8")
    if MARCA not in html:
        raise SystemExit(f"La plantilla {plantilla} no tiene la marca {MARCA}.")

    # Las reglas de exclusion viajan con el tablero para que la carga desde el
    # navegador aplique exactamente el mismo criterio que el analisis en Python.
    reglas = ""
    if EXCLUSIONES.exists():
        with open(EXCLUSIONES, encoding="utf-8") as f:
            lista = json.dumps(json.load(f).get("exclusiones", []),
                               separators=(",", ":"), ensure_ascii=False)
            reglas = lista[1:-1]  # el marcador ya esta entre corchetes
    html = html.replace(MARCA_EXCLUSIONES, reglas)

    # El lector de Excel se incrusta en la pagina. Asi no hay peticion que una red
    # corporativa pueda bloquear, ni ruta relativa que se pueda romper.
    if LECTOR.exists():
        codigo = LECTOR.read_text(encoding="utf-8")
        if "</script" in codigo.lower():
            raise SystemExit("El lector contiene '</script' y no se puede incrustar tal cual.")
        html = html.replace(MARCA_LECTOR, codigo)

    # Un "</" dentro de los datos cerraria la etiqueta <script> antes de tiempo.
    salida.write_text(html.replace(MARCA, datos.replace("</", "<\\/")), encoding="utf-8")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("datos", type=Path, nargs="?", help="JSON generado por preparar_datos_web.py")
    p.add_argument("--excel", type=Path, default=None,
                   help="Excel de origen: prepara los datos y arma el tablero de una vez.")
    p.add_argument("--vacio", action="store_true",
                   help="Arma el tablero SIN datos: cada quien carga su Excel en el "
                        "navegador. Es la version que se publica en GitHub Pages.")
    p.add_argument("-o", "--salida", type=Path, default=Path("tablero_diferencias.html"))
    p.add_argument("--plantilla", type=Path, default=RAIZ / "plantilla.html")
    args = p.parse_args(argv)

    if args.vacio:
        # Sin datos incrustados el tablero muestra la pantalla de carga.
        datos = ""
    elif args.excel:
        sys.path.insert(0, str(RAIZ.parent))
        from preparar_datos_web import construye
        datos = json.dumps(construye(args.excel, "Hoja1", "Hoja2"),
                           separators=(",", ":"), ensure_ascii=False)
    elif args.datos:
        datos = args.datos.read_text(encoding="utf-8")
    else:
        raise SystemExit("Indique el JSON de datos, use --excel con el archivo original, "
                         "o --vacio para la version de GitHub Pages.")

    construir(datos, args.plantilla, args.salida)
    peso = args.salida.stat().st_size / 1024
    print(f"Tablero {'vacio ' if args.vacio else ''}listo: {args.salida.resolve()} "
          f"({peso/1024:.2f} MB)" if peso > 1024 else
          f"Tablero {'vacio ' if args.vacio else ''}listo: {args.salida.resolve()} "
          f"({peso:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
