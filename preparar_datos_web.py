#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convierte el Excel de diferencias en un JSON compacto para el dashboard web.

El dashboard filtra y calcula todo en el navegador, asi que aqui solo se
normaliza y se comprime: los textos que se repiten (tiendas, pickers,
materiales) se guardan una sola vez en diccionarios y cada linea referencia
su posicion. Eso baja el archivo de varios MB a unos cientos de KB.

Uso:
    python preparar_datos_web.py INFORME_DIFERENCIAS.xlsx -o datos.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from informe_diferencias import (CUADRANTES_CAVA, aplica_exclusiones,
                                 carga_despachos, carga_diferencias,
                                 carga_exclusiones, filtra_cuadrantes)


# Etiqueta de las diferencias cuya entrega no aparece en la hoja de despachos.
SIN_CRUCE = "SIN CRUCE DE DESPACHO"


def resume_excluidas(excluidas) -> dict:
    """Lo que se dejo por fuera, para que el tablero pueda declararlo."""
    if excluidas is None or excluidas.empty:
        return {"lineas": 0, "valor": 0.0, "detalle": []}
    return {
        "lineas": int(len(excluidas)),
        "valor": float(-excluidas["VALOR"].clip(upper=0).sum()),
        "detalle": [{
            "fecha": f["FECHA"].strftime("%Y-%m-%d") if pd.notna(f["FECHA"]) else None,
            "tienda": str(f["TIENDA"]),
            "material": str(f["DESCRIPCION MATERIAL"]),
            "unidades": float(f["UNIDADES"]) if pd.notna(f["UNIDADES"]) else None,
            "valor": float(f["VALOR"]),
            "motivo": str(f.get("MOTIVO", "")),
        } for _, f in excluidas.iterrows()],
    }


def indexa(serie: pd.Series) -> tuple[list[str], list[int]]:
    """Convierte una columna de texto en (diccionario, lista de indices)."""
    valores = serie.fillna("(sin dato)").astype(str)
    unicos = sorted(valores.unique())
    posicion = {v: i for i, v in enumerate(unicos)}
    return unicos, [posicion[v] for v in valores]


def construye(entrada: Path, hoja_dif="Hoja1", hoja_des="Hoja2",
              cuadrantes=CUADRANTES_CAVA) -> dict:
    """Lee el Excel y devuelve el JSON compacto del tablero."""
    diferencias = filtra_cuadrantes(carga_diferencias(entrada, hoja_dif), cuadrantes)
    diferencias, excluidas = aplica_exclusiones(diferencias, carga_exclusiones())
    despachos = carga_despachos(entrada, hoja_des)
    df = diferencias.merge(despachos, on="N ENTREGA", how="left")
    return empaqueta(df, despachos, cuadrantes, excluidas)


def empaqueta(df: pd.DataFrame, despachos: pd.DataFrame,
              cuadrantes=CUADRANTES_CAVA,
              excluidas: pd.DataFrame | None = None) -> dict:
    """Comprime un cruce ya hecho al formato que consume el tablero web."""
    df = df.copy()
    df["PICKER"] = df["PICKER"].fillna(SIN_CRUCE)
    df["FECHA"] = pd.to_datetime(df["FECHA"], errors="coerce")
    df = df[df["VALOR"].notna()].copy()

    materiales = (
        df[["CODIGO MATERIAL", "DESCRIPCION MATERIAL"]]
        .drop_duplicates(subset=["CODIGO MATERIAL"])
        .set_index("CODIGO MATERIAL")["DESCRIPCION MATERIAL"]
        .to_dict()
    )

    dic_picker, ix_picker = indexa(df["PICKER"])
    dic_tienda, ix_tienda = indexa(df["TIENDA"])
    dic_cuadrante, ix_cuadrante = indexa(df["CUADRANTE"])
    dic_estado, ix_estado = indexa(df["ESTADO"])
    dic_causal, ix_causal = indexa(df["CAUSAL"])
    dic_ruta, ix_ruta = indexa(df["RUTA"])

    codigos = df["CODIGO MATERIAL"].fillna(0).astype("int64")
    dic_material_cod = sorted(codigos.unique())
    pos_material = {c: i for i, c in enumerate(dic_material_cod)}
    ix_material = [pos_material[c] for c in codigos]
    dic_material_desc = [
        str(materiales.get(c, "(sin descripcion)")) for c in dic_material_cod
    ]

    # Las fechas se guardan como dias transcurridos desde la primera.
    fechas = df["FECHA"]
    origen = fechas.min().normalize()
    dias = ((fechas - origen).dt.days).fillna(-1).astype(int).tolist()

    # Exposicion por picker: entregas y cajas despachadas en el periodo.
    # Aqui un vacio significa "la planilla no anoto quien fue", que no es lo
    # mismo que una entrega que ni siquiera aparece en la hoja de despachos.
    despachos = despachos.copy()
    despachos["PICKER"] = despachos["PICKER"].fillna("SIN PICKER")
    exposicion = (
        despachos.groupby("PICKER")
        .agg(entregas=("N ENTREGA", "nunique"), cajas=("CAJAS", "sum"))
        .reset_index()
    )
    exposicion = {
        str(f["PICKER"]): {"entregas": int(f["entregas"]), "cajas": float(f["cajas"] or 0)}
        for _, f in exposicion.iterrows()
    }

    f_des = despachos["FECHA DESPACHO"].dropna()
    cuadrantes_des = sorted(despachos["CUADRANTE DESPACHO"].dropna().unique().tolist())

    return {
        "generado": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "cuadrantesAnalizados": list(cuadrantes),
        "excluidas": resume_excluidas(excluidas),
        "origenFecha": origen.strftime("%Y-%m-%d"),
        "dic": {
            "picker": dic_picker,
            "tienda": dic_tienda,
            "cuadrante": dic_cuadrante,
            "estado": dic_estado,
            "causal": dic_causal,
            "ruta": dic_ruta,
            "materialCodigo": [int(c) for c in dic_material_cod],
            "materialDesc": dic_material_desc,
        },
        "cols": {
            "dia": dias,
            "picker": ix_picker,
            "tienda": ix_tienda,
            "cuadrante": ix_cuadrante,
            "estado": ix_estado,
            "causal": ix_causal,
            "ruta": ix_ruta,
            "material": ix_material,
            "unidades": [int(v) for v in df["UNIDADES"].fillna(0)],
            "valor": [int(round(v)) for v in df["VALOR"].fillna(0)],
            "entrega": df["N ENTREGA"].fillna("").astype(str).tolist(),
        },
        "exposicion": exposicion,
        "cobertura": {
            "despachoDesde": f_des.min().strftime("%Y-%m-%d") if not f_des.empty else None,
            "despachoHasta": f_des.max().strftime("%Y-%m-%d") if not f_des.empty else None,
            "cuadrantes": cuadrantes_des,
            "entregas": int(despachos["N ENTREGA"].nunique()),
        },
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("entrada", type=Path)
    p.add_argument("-o", "--salida", type=Path, default=Path("datos.json"))
    p.add_argument("--hoja-diferencias", default="Hoja1")
    p.add_argument("--hoja-despachos", default="Hoja2")
    p.add_argument("--cuadrantes", default=",".join(CUADRANTES_CAVA),
                   help=f"Cuadrantes a incluir. Por defecto los de cava: {', '.join(CUADRANTES_CAVA)}.")
    p.add_argument("--todos-los-cuadrantes", action="store_true")
    args = p.parse_args(argv)

    cuadrantes = () if args.todos_los_cuadrantes else [
        c.strip() for c in args.cuadrantes.split(",") if c.strip()]
    datos = construye(args.entrada, args.hoja_diferencias, args.hoja_despachos, cuadrantes)
    args.salida.write_text(json.dumps(datos, separators=(",", ":"), ensure_ascii=False),
                           encoding="utf-8")
    n = len(datos["cols"]["valor"])
    print(f"{n:,} lineas -> {args.salida} "
          f"({args.salida.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
