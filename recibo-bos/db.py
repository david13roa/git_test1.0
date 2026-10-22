"""Conexión y esquema de la base de datos SQLite de Recibo BOS."""
import os
import sqlite3

RUTA_DB = os.environ.get(
    "RECIBO_BOS_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos", "recibo_bos.db"),
)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS materiales (
    material         INTEGER PRIMARY KEY,
    descripcion      TEXT NOT NULL,
    ump              TEXT,
    ums              TEXT,
    cuadrante        TEXT,
    ubicacion        TEXT,
    tendidos         INTEGER,
    pisos            INTEGER,
    cajas_estiba     INTEGER,
    vida_util_cedi   INTEGER,
    vida_util_tienda INTEGER,
    categoria        TEXT,
    ean              TEXT,
    actualizado      TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS ix_materiales_ean ON materiales(ean);

-- Maestro general de SAP (hoja Mdt): sirve para precargar materiales nuevos.
CREATE TABLE IF NOT EXISTS maestro (
    material    INTEGER PRIMARY KEY,
    descripcion TEXT,
    ean         TEXT,
    ums         TEXT,
    ump         TEXT,
    categoria   TEXT
);
CREATE INDEX IF NOT EXISTS ix_maestro_ean ON maestro(ean);

CREATE TABLE IF NOT EXISTS personal (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS recibos (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_hora        TEXT NOT NULL,
    fecha             TEXT NOT NULL,
    oc                TEXT NOT NULL,
    material          INTEGER NOT NULL,
    descripcion       TEXT,
    cantidad          INTEGER NOT NULL,
    cajas_estiba      INTEGER NOT NULL,
    vencimiento       TEXT,
    lote              TEXT,
    auxiliar          TEXT,
    estibas_completas INTEGER NOT NULL,
    saldo             INTEGER NOT NULL,
    vida_min          INTEGER,
    dias_vida_llegada INTEGER,
    status_entrada    TEXT,
    cuadrante         TEXT,
    ubicacion         TEXT,
    autorizado_por    TEXT,
    observacion       TEXT,
    anulado           INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_recibos_fecha ON recibos(fecha);
CREATE INDEX IF NOT EXISTS ix_recibos_oc ON recibos(oc);

CREATE TABLE IF NOT EXISTS config (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
"""

# Columnas agregadas después de la primera versión: se crean en bases existentes.
MIGRACIONES = {
    "recibos": {"tiempo_captura_seg": "INTEGER"},
}

DIAS_RESPALDO = 30


def conectar():
    os.makedirs(os.path.dirname(RUTA_DB), exist_ok=True)
    con = sqlite3.connect(RUTA_DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def inicializar():
    with conectar() as con:
        con.executescript(ESQUEMA)
        for tabla, columnas in MIGRACIONES.items():
            existentes = {r["name"] for r in con.execute(f"PRAGMA table_info({tabla})")}
            for columna, tipo in columnas.items():
                if columna not in existentes:
                    con.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")


def leer_config(clave, defecto=None):
    with conectar() as con:
        fila = con.execute("SELECT valor FROM config WHERE clave=?", (clave,)).fetchone()
    return fila["valor"] if fila else defecto


def guardar_config(clave, valor):
    with conectar() as con:
        con.execute("INSERT INTO config VALUES (?, ?) ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
                    (clave, valor))


def respaldar(hoy):
    """Copia la base a datos/respaldos una vez al día y conserva los últimos DIAS_RESPALDO días."""
    carpeta = os.path.join(os.path.dirname(RUTA_DB), "respaldos")
    destino = os.path.join(carpeta, f"recibo_bos_{hoy.isoformat()}.db")
    if os.path.exists(destino):
        return None
    os.makedirs(carpeta, exist_ok=True)
    origen = conectar()
    copia = sqlite3.connect(destino)
    try:
        origen.backup(copia)
    finally:
        copia.close()
        origen.close()
    antiguos = sorted(f for f in os.listdir(carpeta) if f.startswith("recibo_bos_") and f.endswith(".db"))
    for viejo in antiguos[:-DIAS_RESPALDO]:
        os.remove(os.path.join(carpeta, viejo))
    return destino
