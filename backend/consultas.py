# -*- coding: utf-8 -*-
"""
Agregaciones que responde la API. Todas reciben el DataFrame ya filtrado y
devuelven listas de diccionarios listas para serializar.

Los faltantes se reportan como costo positivo; los sobrantes como positivos
tambien, pero en su propia columna. El impacto neto es sobrantes menos
faltantes (negativo cuando hubo perdida).
"""

from __future__ import annotations

import pandas as pd

from backend.almacen import SIN_CRUCE


def _parte(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["_falt"] = d["VALOR"].where(d["VALOR"] < 0, 0).abs()
    d["_sobr"] = d["VALOR"].where(d["VALOR"] > 0, 0)
    d["_uf"] = d["UNIDADES"].where(d["UNIDADES"] < 0, 0).abs()
    d["_us"] = d["UNIDADES"].where(d["UNIDADES"] > 0, 0)
    return d


def _agrupa(df: pd.DataFrame, llaves: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=llaves + ["lineas", "faltantes", "sobrantes",
                                              "unidadesFaltantes", "unidadesSobrantes",
                                              "tiendas", "materiales", "entregas"])
    d = _parte(df)
    g = d.groupby(llaves, dropna=False).agg(
        lineas=("VALOR", "size"),
        faltantes=("_falt", "sum"),
        sobrantes=("_sobr", "sum"),
        unidadesFaltantes=("_uf", "sum"),
        unidadesSobrantes=("_us", "sum"),
        tiendas=("TIENDA", "nunique"),
        materiales=("CODIGO MATERIAL", "nunique"),
        entregas=("N ENTREGA", "nunique"),
    ).reset_index()
    g["impactoNeto"] = g["sobrantes"] - g["faltantes"]
    g["impactoAbsoluto"] = g["faltantes"] + g["sobrantes"]
    return g


def resumen(df: pd.DataFrame, cobertura: dict, cuadrantes) -> dict:
    d = _parte(df)
    falt = float(d["_falt"].sum())
    sobr = float(d["_sobr"].sum())
    con_picker = d[d["PICKER"] != SIN_CRUCE]
    atribuido = float(con_picker["_falt"].sum())
    fechas = df["FECHA"].dropna()
    return {
        "cuadrantes": list(cuadrantes),
        "desde": fechas.min().date().isoformat() if not fechas.empty else None,
        "hasta": fechas.max().date().isoformat() if not fechas.empty else None,
        "dias": int(fechas.dt.date.nunique()) if not fechas.empty else 0,
        "lineas": int(len(df)),
        "faltantes": falt,
        "sobrantes": sobr,
        "impactoNeto": sobr - falt,
        "impactoAbsoluto": falt + sobr,
        "unidadesFaltantes": float(d["_uf"].sum()),
        "unidadesSobrantes": float(d["_us"].sum()),
        "tiendas": int(df["TIENDA"].nunique()),
        "materiales": int(df["CODIGO MATERIAL"].nunique()),
        "lineasConPicker": int(len(con_picker)),
        "lineasSinCruce": int(len(df) - len(con_picker)),
        "pctAtribuido": round(100 * len(con_picker) / len(df), 1) if len(df) else 0.0,
        "costoAtribuido": atribuido,
        "costoSinResponsable": falt - atribuido,
        "pickers": int(con_picker["PICKER"].nunique()),
        "cobertura": cobertura,
    }


def pickers(df: pd.DataFrame, exposicion: dict) -> list[dict]:
    g = _agrupa(df, ["PICKER"])
    if g.empty:
        return []
    filas = []
    for _, f in g.iterrows():
        nombre = str(f["PICKER"])
        exp = exposicion.get(nombre, {"entregas": 0, "cajas": 0})
        sin_cruce = nombre == SIN_CRUCE
        filas.append({
            "picker": nombre, "sinCruce": sin_cruce,
            "lineas": int(f["lineas"]),
            "faltantes": float(f["faltantes"]), "sobrantes": float(f["sobrantes"]),
            "impactoNeto": float(f["impactoNeto"]), "impactoAbsoluto": float(f["impactoAbsoluto"]),
            "unidadesFaltantes": float(f["unidadesFaltantes"]),
            "unidadesSobrantes": float(f["unidadesSobrantes"]),
            "tiendas": int(f["tiendas"]), "materiales": int(f["materiales"]),
            "entregasConDiferencia": int(f["entregas"]),
            "entregasDespachadas": exp["entregas"] or None,
            "cajasDespachadas": exp["cajas"] or None,
            "pctEntregasConDiferencia": round(100 * f["entregas"] / exp["entregas"], 1)
                                        if exp["entregas"] else None,
            "costoPorCaja": round(f["faltantes"] / exp["cajas"]) if exp["cajas"] else None,
            "costoPorEntrega": round(f["faltantes"] / exp["entregas"]) if exp["entregas"] else None,
        })

    # La fila sin cruce no es un picker: queda de ultima y no entra en la base
    # del porcentaje, pero se conserva para que ningun peso quede escondido.
    filas.sort(key=lambda x: (x["sinCruce"], -x["faltantes"]))
    base = sum(x["faltantes"] for x in filas if not x["sinCruce"])
    acumulado = 0.0
    puesto = 0
    for f in filas:
        if f["sinCruce"]:
            f["puesto"] = f["pctDelCosto"] = f["pctAcumulado"] = None
            continue
        puesto += 1
        f["puesto"] = puesto
        f["pctDelCosto"] = round(100 * f["faltantes"] / base, 1) if base else 0.0
        acumulado += f["pctDelCosto"]
        f["pctAcumulado"] = round(acumulado, 1)
    return filas


def picker_por_tienda(df: pd.DataFrame, incluir_sin_cruce=False) -> list[dict]:
    if not incluir_sin_cruce:
        df = df[df["PICKER"] != SIN_CRUCE]
    g = _agrupa(df, ["PICKER", "TIENDA"]).sort_values("faltantes", ascending=False)
    return [{"picker": str(f["PICKER"]), "tienda": str(f["TIENDA"]),
             "lineas": int(f["lineas"]), "faltantes": float(f["faltantes"]),
             "sobrantes": float(f["sobrantes"]), "impactoNeto": float(f["impactoNeto"]),
             "unidadesFaltantes": float(f["unidadesFaltantes"]),
             "entregas": int(f["entregas"])}
            for _, f in g.iterrows()]


def tiendas(df: pd.DataFrame) -> list[dict]:
    g = _agrupa(df, ["TIENDA"]).sort_values("faltantes", ascending=False)
    dominante = {}
    for f in picker_por_tienda(df):
        if f["tienda"] not in dominante:
            dominante[f["tienda"]] = f
    filas = []
    for i, (_, f) in enumerate(g.iterrows(), start=1):
        nombre = str(f["TIENDA"])
        top = dominante.get(nombre)
        filas.append({
            "puesto": i, "tienda": nombre, "lineas": int(f["lineas"]),
            "faltantes": float(f["faltantes"]), "sobrantes": float(f["sobrantes"]),
            "impactoNeto": float(f["impactoNeto"]),
            "unidadesFaltantes": float(f["unidadesFaltantes"]),
            "materiales": int(f["materiales"]),
            "pickerConMayorImpacto": top["picker"] if top else None,
            "valorDelPicker": top["faltantes"] if top else None,
        })
    return filas


def materiales(df: pd.DataFrame, limite: int | None = None) -> list[dict]:
    g = _agrupa(df, ["CODIGO MATERIAL", "DESCRIPCION MATERIAL"]).sort_values(
        "faltantes", ascending=False)
    if limite:
        g = g.head(limite)
    return [{"puesto": i, "codigo": int(f["CODIGO MATERIAL"]),
             "material": str(f["DESCRIPCION MATERIAL"]), "lineas": int(f["lineas"]),
             "faltantes": float(f["faltantes"]), "sobrantes": float(f["sobrantes"]),
             "unidadesFaltantes": float(f["unidadesFaltantes"]),
             "tiendas": int(f["tiendas"])}
            for i, (_, f) in enumerate(g.iterrows(), start=1)]


def serie_diaria(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    d = _parte(df)
    d["_dia"] = d["FECHA"].dt.date
    g = d.groupby("_dia").agg(faltantes=("_falt", "sum"), sobrantes=("_sobr", "sum"),
                              lineas=("VALOR", "size")).reset_index().sort_values("_dia")
    return [{"fecha": f["_dia"].isoformat(), "faltantes": float(f["faltantes"]),
             "sobrantes": float(f["sobrantes"]), "lineas": int(f["lineas"])}
            for _, f in g.iterrows()]


def detalle(df: pd.DataFrame, pagina: int, por_pagina: int) -> dict:
    orden = df.sort_values("VALOR")
    total = len(orden)
    inicio = max(0, (pagina - 1) * por_pagina)
    trozo = orden.iloc[inicio:inicio + por_pagina]
    filas = [{
        "fecha": f["FECHA"].date().isoformat() if pd.notna(f["FECHA"]) else None,
        "picker": str(f["PICKER"]), "tienda": str(f["TIENDA"]),
        "cuadrante": str(f["CUADRANTE"]), "ruta": str(f["RUTA"]),
        "entrega": str(f["N ENTREGA"]) if pd.notna(f["N ENTREGA"]) else None,
        "codigo": int(f["CODIGO MATERIAL"]) if pd.notna(f["CODIGO MATERIAL"]) else None,
        "material": str(f["DESCRIPCION MATERIAL"]),
        "unidades": float(f["UNIDADES"]) if pd.notna(f["UNIDADES"]) else None,
        "precioUnitario": float(f["PRECIO UNITARIO"]) if pd.notna(f["PRECIO UNITARIO"]) else None,
        "valor": float(f["VALOR"]),
        "tipo": "FALTANTE" if f["VALOR"] < 0 else "SOBRANTE",
        "estado": str(f["ESTADO"]), "causal": str(f["CAUSAL"]),
    } for _, f in trozo.iterrows()]
    return {"total": total, "pagina": pagina, "porPagina": por_pagina,
            "paginas": max(1, -(-total // por_pagina)), "filas": filas}


def filtros_disponibles(dataset) -> dict:
    df = dataset.lineas
    fechas = df["FECHA"].dropna()
    return {
        "pickers": sorted(p for p in df["PICKER"].dropna().unique() if p != SIN_CRUCE),
        "tiendas": sorted(df["TIENDA"].dropna().unique().tolist()),
        "cuadrantes": sorted(df["CUADRANTE"].dropna().unique().tolist()),
        "estados": sorted(df["ESTADO"].dropna().unique().tolist()),
        "causales": sorted(df["CAUSAL"].dropna().unique().tolist()),
        "fechaMinima": fechas.min().date().isoformat() if not fechas.empty else None,
        "fechaMaxima": fechas.max().date().isoformat() if not fechas.empty else None,
    }
