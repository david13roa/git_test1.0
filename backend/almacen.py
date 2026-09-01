# -*- coding: utf-8 -*-
"""
Dataset activo del servidor: lo carga desde el Excel, lo deja en memoria y
aplica los filtros que llegan por la API.

El Excel de origen se guarda en disco (`datos/activo.xlsx`) para que el
servidor recupere el ultimo cargado al reiniciarse.
"""

from __future__ import annotations

import shutil
import threading
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from informe_diferencias import (CUADRANTES_CAVA, carga_despachos,
                                 carga_diferencias, filtra_cuadrantes)

SIN_CRUCE = "SIN CRUCE DE DESPACHO"


class DatosInvalidos(ValueError):
    """El archivo se leyo bien pero no sirve para el analisis."""
RAIZ = Path(__file__).resolve().parent.parent
CARPETA_DATOS = RAIZ / "datos"
EXCEL_ACTIVO = CARPETA_DATOS / "activo.xlsx"


@dataclass
class Filtros:
    desde: date | None = None
    hasta: date | None = None
    estado: str | None = "APLICA"
    picker: str | None = None
    tienda: str | None = None
    cuadrante: str | None = None
    buscar: str | None = None
    solo_cobertura: bool = False


@dataclass
class Dataset:
    """Todo lo que el servidor necesita tener listo en memoria."""
    lineas: pd.DataFrame
    despachos: pd.DataFrame
    cuadrantes: tuple[str, ...]
    origen: str
    generado: pd.Timestamp = field(default_factory=pd.Timestamp.now)

    @property
    def cobertura(self) -> dict:
        fechas = self.despachos["FECHA DESPACHO"].dropna()
        cuadrantes = sorted(self.despachos["CUADRANTE DESPACHO"].dropna().unique())
        return {
            "despachoDesde": fechas.min().date().isoformat() if not fechas.empty else None,
            "despachoHasta": fechas.max().date().isoformat() if not fechas.empty else None,
            "cuadrantes": [str(c) for c in cuadrantes],
            "entregas": int(self.despachos["N ENTREGA"].nunique()),
        }

    @property
    def exposicion(self) -> dict:
        g = self.despachos.groupby("PICKER").agg(
            entregas=("N ENTREGA", "nunique"), cajas=("CAJAS", "sum"))
        return {str(k): {"entregas": int(v.entregas), "cajas": float(v.cajas or 0)}
                for k, v in g.iterrows()}


class Almacen:
    """Guarda el dataset activo. Es seguro llamarlo desde varias peticiones."""

    def __init__(self, cuadrantes=CUADRANTES_CAVA):
        self._cuadrantes = tuple(cuadrantes)
        self._dataset: Dataset | None = None
        self._candado = threading.Lock()

    # ---------------------------------------------------------------- carga

    def construye(self, ruta: Path, hoja_dif="Hoja1", hoja_des="Hoja2",
                  nombre: str | None = None) -> Dataset:
        diferencias = filtra_cuadrantes(carga_diferencias(ruta, hoja_dif), self._cuadrantes)
        despachos = carga_despachos(ruta, hoja_des)
        despachos["PICKER"] = despachos["PICKER"].fillna("SIN PICKER")

        lineas = diferencias.merge(despachos, on="N ENTREGA", how="left")
        lineas["PICKER"] = lineas["PICKER"].fillna(SIN_CRUCE)
        lineas["RUTA"] = lineas["RUTA"].fillna("(sin dato)")
        lineas = lineas[lineas["VALOR"].notna()].reset_index(drop=True)
        if lineas.empty:
            raise DatosInvalidos(
                "El archivo no tiene ninguna linea de diferencia en los cuadrantes "
                f"{', '.join(self._cuadrantes)}.")
        return Dataset(lineas, despachos, self._cuadrantes, nombre or ruta.name)

    def carga(self, ruta: Path) -> Dataset:
        dataset = self.construye(ruta)
        with self._candado:
            self._dataset = dataset
        return dataset

    def reemplaza(self, ruta_temporal: Path, nombre: str | None = None) -> Dataset:
        """Valida el archivo nuevo ANTES de pisar el que esta en uso."""
        dataset = self.construye(ruta_temporal, nombre=nombre)
        CARPETA_DATOS.mkdir(exist_ok=True)
        shutil.copyfile(ruta_temporal, EXCEL_ACTIVO)
        with self._candado:
            self._dataset = dataset
        return dataset

    def carga_inicial(self) -> Dataset | None:
        if EXCEL_ACTIVO.exists():
            try:
                return self.carga(EXCEL_ACTIVO)
            except Exception:
                return None
        return None

    @property
    def dataset(self) -> Dataset:
        with self._candado:
            if self._dataset is None:
                raise LookupError(
                    "Todavia no hay datos cargados. Suba el Excel con POST /api/cargar.")
            return self._dataset

    @property
    def hay_datos(self) -> bool:
        return self._dataset is not None

    # ------------------------------------------------------------- filtrado

    def filtra(self, f: Filtros) -> pd.DataFrame:
        d = self.dataset
        df = d.lineas

        if f.solo_cobertura:
            cob = d.cobertura
            if cob["despachoDesde"]:
                df = df[(df["FECHA"] >= pd.Timestamp(cob["despachoDesde"]))
                        & (df["FECHA"] < pd.Timestamp(cob["despachoHasta"]) + pd.Timedelta(days=1))]
            if cob["cuadrantes"]:
                df = df[df["CUADRANTE"].apply(
                    lambda c: any(q in str(c) for q in cob["cuadrantes"]))]
        if f.desde:
            df = df[df["FECHA"] >= pd.Timestamp(f.desde)]
        if f.hasta:
            df = df[df["FECHA"] < pd.Timestamp(f.hasta) + pd.Timedelta(days=1)]
        if f.estado:
            df = df[df["ESTADO"] == f.estado.strip().upper()]
        if f.picker:
            df = df[df["PICKER"] == f.picker.strip().upper()]
        if f.tienda:
            df = df[df["TIENDA"] == f.tienda.strip().upper()]
        if f.cuadrante:
            df = df[df["CUADRANTE"] == f.cuadrante.strip().upper()]
        if f.buscar:
            texto = f.buscar.strip().lower()
            df = df[df["DESCRIPCION MATERIAL"].str.lower().str.contains(texto, na=False)
                    | df["CODIGO MATERIAL"].astype(str).str.contains(texto, na=False)]
        return df


ALMACEN = Almacen()
