# -*- coding: utf-8 -*-
"""
API del control de diferencias de despacho.

Levantar en desarrollo:
    uvicorn backend.main:app --reload

Levantar para la red interna de la empresa:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000

La documentacion interactiva queda en /docs.
"""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from backend import consultas
from backend.almacen import ALMACEN, DatosInvalidos, Filtros
from informe_diferencias import (CUADRANTES_CAVA, Datos, construye_resumen,
                                 exporta, picker_por_tienda, ranking_pickers,
                                 ranking_tiendas, top_materiales)
from preparar_datos_web import empaqueta, resume_excluidas

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / "tablero" / "plantilla.html"
EXTENSIONES = {".xlsx", ".xlsm", ".xls"}
TAMANO_MAXIMO = 60 * 1024 * 1024  # 60 MB

app = FastAPI(
    title="Control de diferencias de despacho",
    description=("Diferencias de inventario de cava (congelados, nevera y fruver nevera) "
                 "cruzadas con el picker responsable de cada entrega."),
    version="1.0.0",
)


@app.on_event("startup")
def arranque():
    ALMACEN.carga_inicial()


# --------------------------------------------------------------------------- #
# Filtros compartidos por todas las consultas
# --------------------------------------------------------------------------- #

def filtros(
    desde: date | None = Query(None, description="Fecha inicial, inclusive."),
    hasta: date | None = Query(None, description="Fecha final, inclusive."),
    estado: str | None = Query("APLICA", description="APLICA, NO APLICA, PENDIENTE. "
                                                     "Vacio para no filtrar."),
    picker: str | None = Query(None),
    tienda: str | None = Query(None),
    cuadrante: str | None = Query(None),
    buscar: str | None = Query(None, description="Texto o codigo de material."),
    solo_cobertura: bool = Query(False, alias="soloCobertura",
                                 description="Limita al periodo y los cuadrantes que "
                                             "cubre la hoja de despachos."),
) -> Filtros:
    return Filtros(desde=desde, hasta=hasta, estado=estado or None, picker=picker,
                   tienda=tienda, cuadrante=cuadrante, buscar=buscar,
                   solo_cobertura=solo_cobertura)


def _datos_o_error():
    try:
        return ALMACEN.dataset
    except LookupError as e:
        raise HTTPException(status_code=409, detail=str(e))


def _filtrado(f: Filtros) -> pd.DataFrame:
    _datos_o_error()
    return ALMACEN.filtra(f)


# --------------------------------------------------------------------------- #
# Estado del servicio
# --------------------------------------------------------------------------- #

@app.get("/api/salud", tags=["estado"], summary="Verifica que el servicio responde")
def salud():
    return {"estado": "ok", "hayDatos": ALMACEN.hay_datos}


@app.get("/api/meta", tags=["estado"], summary="Que archivo esta cargado y que cubre")
def meta():
    d = _datos_o_error()
    fechas = d.lineas["FECHA"].dropna()
    return {
        "origen": d.origen,
        "generado": d.generado.strftime("%Y-%m-%d %H:%M"),
        "cuadrantes": list(d.cuadrantes),
        "lineas": int(len(d.lineas)),
        "desde": fechas.min().date().isoformat() if not fechas.empty else None,
        "hasta": fechas.max().date().isoformat() if not fechas.empty else None,
        "cobertura": d.cobertura,
        "excluidas": resume_excluidas(d.excluidas),
    }


@app.get("/api/exclusiones", tags=["estado"],
         summary="Lineas descartadas por error de captura y su motivo")
def exclusiones():
    return resume_excluidas(_datos_o_error().excluidas)


@app.get("/api/filtros", tags=["estado"], summary="Valores disponibles para filtrar")
def filtros_disponibles():
    return consultas.filtros_disponibles(_datos_o_error())


# --------------------------------------------------------------------------- #
# Consultas
# --------------------------------------------------------------------------- #

@app.get("/api/resumen", tags=["consultas"], summary="Indicadores generales")
def resumen(f: Filtros = Depends(filtros)):
    d = _datos_o_error()
    salida = consultas.resumen(_filtrado(f), d.cobertura, d.cuadrantes)
    salida["excluidas"] = resume_excluidas(d.excluidas)
    return salida


@app.get("/api/pickers", tags=["consultas"],
         summary="Ranking de pickers con su costo y sus indicadores por volumen")
def pickers(f: Filtros = Depends(filtros)):
    d = _datos_o_error()
    return consultas.pickers(_filtrado(f), d.exposicion)


@app.get("/api/picker-tienda", tags=["consultas"],
         summary="Que picker tiene diferencias en cada tienda y por cuanto")
def picker_tienda(f: Filtros = Depends(filtros),
                  incluir_sin_cruce: bool = Query(False, alias="incluirSinCruce")):
    return consultas.picker_por_tienda(_filtrado(f), incluir_sin_cruce)


@app.get("/api/tiendas", tags=["consultas"], summary="Ranking de tiendas")
def tiendas(f: Filtros = Depends(filtros)):
    return consultas.tiendas(_filtrado(f))


@app.get("/api/materiales", tags=["consultas"], summary="Materiales que mas se pierden")
def materiales(f: Filtros = Depends(filtros),
               limite: int | None = Query(None, ge=1, le=5000)):
    return consultas.materiales(_filtrado(f), limite)


@app.get("/api/serie-diaria", tags=["consultas"], summary="Costo por dia de despacho")
def serie_diaria(f: Filtros = Depends(filtros)):
    return consultas.serie_diaria(_filtrado(f))


@app.get("/api/detalle", tags=["consultas"], summary="Diferencias linea a linea")
def detalle(f: Filtros = Depends(filtros),
            pagina: int = Query(1, ge=1),
            por_pagina: int = Query(50, ge=1, le=1000, alias="porPagina")):
    return consultas.detalle(_filtrado(f), pagina, por_pagina)


@app.get("/api/datos", tags=["consultas"],
         summary="Dataset comprimido que consume el tablero web")
def datos():
    return JSONResponse(_paquete_web())


# --------------------------------------------------------------------------- #
# Cargar un Excel nuevo
# --------------------------------------------------------------------------- #

@app.post("/api/cargar", tags=["administracion"],
          summary="Reemplaza el dataset activo con un Excel nuevo")
async def cargar(archivo: UploadFile = File(..., description="Excel con Hoja1 y Hoja2.")):
    if Path(archivo.filename or "").suffix.lower() not in EXTENSIONES:
        raise HTTPException(status_code=415,
                            detail=f"Formato no admitido. Use {', '.join(sorted(EXTENSIONES))}.")
    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo llego vacio.")
    if len(contenido) > TAMANO_MAXIMO:
        raise HTTPException(status_code=413,
                            detail=f"El archivo supera {TAMANO_MAXIMO // (1024*1024)} MB.")

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(contenido)
        ruta = Path(tmp.name)
    try:
        # Si el archivo nuevo no sirve, el que ya estaba en uso no se toca.
        dataset = ALMACEN.reemplaza(ruta, Path(archivo.filename).name)
    except DatosInvalidos as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        # No se expone el error interno: casi siempre es un archivo que no es
        # un Excel real, o que no tiene las hojas y columnas esperadas.
        raise HTTPException(
            status_code=422,
            detail="No se pudo leer el archivo. Verifique que sea el Excel de "
                   "diferencias, con la hoja de diferencias y la de despachos.")
    finally:
        ruta.unlink(missing_ok=True)
        _PAQUETE.clear()

    return {"cargado": archivo.filename, "lineas": int(len(dataset.lineas)),
            "cuadrantes": list(dataset.cuadrantes)}


# --------------------------------------------------------------------------- #
# Descargas
# --------------------------------------------------------------------------- #

@app.get("/api/informe.xlsx", tags=["descargas"],
         summary="Genera el informe completo en Excel", response_class=Response)
def informe_excel(f: Filtros = Depends(filtros)):
    d = _datos_o_error()
    df = _filtrado(f)
    if df.empty:
        raise HTTPException(status_code=404, detail="No hay diferencias con esos filtros.")

    con_picker = df[df["PICKER"] != "SIN CRUCE DE DESPACHO"]
    sin_picker = df[df["PICKER"] == "SIN CRUCE DE DESPACHO"]
    datos_informe = Datos(con_picker, d.despachos, sin_picker, {
        "Lineas de diferencia": len(df),
        "Lineas con picker identificado": len(con_picker),
        "Lineas sin picker identificado": len(sin_picker),
        "% lineas atribuidas": round(100 * len(con_picker) / max(len(df), 1), 1),
        "Entregas en hoja de despacho": int(d.despachos["N ENTREGA"].nunique()),
        "Pickers identificados": int(con_picker["PICKER"].nunique()),
    })
    ranking = ranking_pickers(datos_informe, "faltante")

    columnas = ["FECHA", "PICKER", "TIENDA", "CECO", "CUADRANTE", "N ENTREGA", "RUTA",
                "CODIGO MATERIAL", "DESCRIPCION MATERIAL", "UNIDADES", "PRECIO UNITARIO",
                "VALOR", "TIPO DIFERENCIA", "ESTADO", "CAUSAL", "AREA", "GV", "JDZ", "ATIENDE"]

    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "informe.xlsx"
        exporta(ruta, {
            "Resumen": construye_resumen(datos_informe, df, ranking, f.estado or "todos",
                                         "faltante", d.cuadrantes),
            "Ranking Pickers": ranking,
            "Picker x Tienda": picker_por_tienda(datos_informe),
            "Detalle": con_picker.reindex(columns=columnas)
                                 .sort_values(["PICKER", "TIENDA", "VALOR"]),
            "Ranking Tiendas": ranking_tiendas(datos_informe, df),
            "Top Materiales": top_materiales(df),
            "Sin Picker": sin_picker.reindex(
                columns=[c for c in columnas if c not in ("PICKER", "RUTA")])
                .sort_values("VALOR"),
            "Excluidas": d.excluidas.reindex(
                columns=[c for c in columnas if c not in ("PICKER", "RUTA")] + ["MOTIVO"]),
        })
        cuerpo = ruta.read_bytes()

    nombre = f"informe_diferencias_cava_{date.today().isoformat()}.xlsx"
    return Response(
        content=cuerpo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


# --------------------------------------------------------------------------- #
# Tablero
# --------------------------------------------------------------------------- #

_PAQUETE: dict[str, dict] = {}


def _paquete_web() -> dict:
    """JSON compacto del tablero, calculado una vez por dataset."""
    d = _datos_o_error()
    if "actual" not in _PAQUETE:
        _PAQUETE["actual"] = empaqueta(d.lineas, d.despachos, d.cuadrantes,
                                       d.excluidas)
    return _PAQUETE["actual"]


@app.get("/", tags=["tablero"], response_class=HTMLResponse,
         summary="Tablero interactivo")
def tablero():
    if not PLANTILLA.exists():
        raise HTTPException(status_code=500, detail=f"Falta la plantilla {PLANTILLA}.")
    html = PLANTILLA.read_text(encoding="utf-8")
    if not ALMACEN.hay_datos:
        return HTMLResponse(
            "<h1 style='font-family:sans-serif'>Todavia no hay datos</h1>"
            "<p style='font-family:sans-serif'>Suba el Excel con "
            "<code>POST /api/cargar</code> o desde <a href='/docs'>/docs</a>.</p>",
            status_code=409)
    datos = json.dumps(_paquete_web(), separators=(",", ":"), ensure_ascii=False)
    return HTMLResponse(html.replace("/*__DATOS__*/", datos.replace("</", "<\\/")))
