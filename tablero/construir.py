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


def construir(datos: str, plantilla: Path, salida: Path) -> None:
    html = plantilla.read_text(encoding="utf-8")
    if MARCA not in html:
        raise SystemExit(f"La plantilla {plantilla} no tiene la marca {MARCA}.")
    # Un "</" dentro de los datos cerraria la etiqueta <script> antes de tiempo.
    salida.write_text(html.replace(MARCA, datos.replace("</", "<\\/")), encoding="utf-8")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("datos", type=Path, nargs="?", help="JSON generado por preparar_datos_web.py")
    p.add_argument("--excel", type=Path, default=None,
                   help="Excel de origen: prepara los datos y arma el tablero de una vez.")
    p.add_argument("-o", "--salida", type=Path, default=Path("tablero_diferencias.html"))
    p.add_argument("--plantilla", type=Path, default=RAIZ / "plantilla.html")
    args = p.parse_args(argv)

    if args.excel:
        sys.path.insert(0, str(RAIZ.parent))
        from preparar_datos_web import construye
        datos = json.dumps(construye(args.excel, "Hoja1", "Hoja2"),
                           separators=(",", ":"), ensure_ascii=False)
    elif args.datos:
        datos = args.datos.read_text(encoding="utf-8")
    else:
        raise SystemExit("Indique el JSON de datos o use --excel con el archivo original.")

    construir(datos, args.plantilla, args.salida)
    print(f"Tablero listo: {args.salida.resolve()} "
          f"({args.salida.stat().st_size/1024/1024:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
