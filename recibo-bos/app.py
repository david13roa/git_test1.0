"""Recibo BOS: aplicación web de recibo de mercancía y rótulos FEFO-FIFO.

Desarrollo:   python app.py
Producción:   waitress-serve --listen=127.0.0.1:8080 app:app   (ver iniciar.bat)
"""
import io
from datetime import date, datetime, timedelta

import openpyxl
import segno
from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for

import db
import importar_excel
import impresora
from logica import a_entero, calcular, codigo_corto, estibas_del_recibo, normalizar_codigo, texto_qr

app = Flask(__name__)
db.inicializar()

CAMPOS_MATERIAL = ["descripcion", "ump", "ums", "cuadrante", "ubicacion", "tendidos", "pisos", "cajas_estiba",
                   "vida_util_cedi", "vida_util_tienda", "categoria", "ean"]
CAMPOS_NUMERICOS = {"tendidos", "pisos", "cajas_estiba", "vida_util_cedi", "vida_util_tienda"}
DIAS_HABILES_MES = 26
NIVELES_TINTA = {
    "normal": "Normal (como el Excel)",
    "ahorro": "Ahorro de tóner: números negros sin negrita y sin fondos grises",
    "gris": "Modo eco: números rellenos en gris y sin fondos grises",
}
# Tono de los números en modo eco: la láser imprime el gris con puntos, así gasta menos tóner que el negro.
TONOS_GRIS = {"oscuro": ("Oscuro", "#555"), "medio": ("Medio", "#777"), "claro": ("Claro", "#999")}
_ultimo_respaldo = None


@app.before_request
def respaldo_diario():
    global _ultimo_respaldo
    hoy = date.today()
    if _ultimo_respaldo != hoy:
        db.respaldar(hoy)
        _ultimo_respaldo = hoy


def _fecha(texto):
    try:
        return date.fromisoformat(texto) if texto else None
    except ValueError:
        return None


def buscar_material(con, codigo):
    """Busca en el portafolio por últimos dígitos, material completo o EAN.

    Si no está en el portafolio pero sí en el maestro de SAP, lo devuelve como sugerencia.
    """
    tipo = normalizar_codigo(codigo)
    if not tipo:
        return None, None
    if tipo[0] == "material":
        fila = con.execute("SELECT * FROM materiales WHERE material=?", (tipo[1],)).fetchone()
        if fila:
            return dict(fila), None
        sugerido = con.execute("SELECT * FROM maestro WHERE material=?", (tipo[1],)).fetchone()
        return None, dict(sugerido) if sugerido else {"material": tipo[1]}
    fila = con.execute("SELECT * FROM materiales WHERE ean=?", (tipo[1],)).fetchone()
    if fila:
        return dict(fila), None
    sugerido = con.execute("SELECT * FROM maestro WHERE ean=?", (tipo[1],)).fetchone()
    if sugerido:
        fila = con.execute("SELECT * FROM materiales WHERE material=?", (sugerido["material"],)).fetchone()
        if fila:
            return dict(fila), None
    return None, dict(sugerido) if sugerido else None


# ---------------------------------------------------------------- páginas

@app.route("/")
def inicio():
    return redirect(url_for("recibo"))


@app.route("/recibo")
def recibo():
    with db.conectar() as con:
        personal = [r["nombre"] for r in con.execute("SELECT nombre FROM personal WHERE activo=1 ORDER BY nombre")]
        hoy = con.execute(
            "SELECT * FROM recibos WHERE fecha=? AND anulado=0 ORDER BY id DESC LIMIT 15",
            (date.today().isoformat(),)).fetchall()
    return render_template("recibo.html", personal=personal, recibos_hoy=hoy, pagina="recibo")


def ajustes_rotulo(args=None):
    """Ahorro de tóner y reverso en blanco guardados en la pantalla Impresora (la vista previa los puede cambiar)."""
    args = args or {}
    tinta = args.get("tinta") or db.leer_config("rotulo_tinta", "gris")
    tinta = "gris" if tinta == "maximo" else tinta  # el contorno de la versión anterior se cambió por gris
    tono = args.get("tono") or db.leer_config("rotulo_tono", "medio")
    reverso = args.get("reverso") if "reverso" in args else db.leer_config("rotulo_reverso_blanco", "")
    tono = tono if tono in TONOS_GRIS else "medio"
    return {"tinta": tinta if tinta in NIVELES_TINTA else "gris", "tono": tono, "color_tono": TONOS_GRIS[tono][1],
            "reverso_blanco": reverso == "1"}


def _render_rotulo(r, estibas):
    vencimiento = _fecha(r["vencimiento"])
    fecha_hora = datetime.fromisoformat(r["fecha_hora"])
    for e in estibas:
        e["qr_texto"] = texto_qr(r["material"], e["cajas"], vencimiento)
        e["qr_svg"] = segno.make(e["qr_texto"], error="m").svg_inline(omitsize=True, border=1)
    return render_template(
        "rotulo.html", r=r, estibas=estibas, codigo=codigo_corto(r["material"]),
        vencimiento=vencimiento.strftime("%d-%m-%Y") if vencimiento else "",
        fecha_hora=fecha_hora, dia_juliano=fecha_hora.timetuple().tm_yday,
        imprimir=request.args.get("imprimir") == "1", ajustes=ajustes_rotulo(request.args),
    )


@app.route("/rotulo/<int:recibo_id>")
def rotulo(recibo_id):
    with db.conectar() as con:
        r = con.execute("SELECT * FROM recibos WHERE id=?", (recibo_id,)).fetchone()
    if not r:
        abort(404)
    r = dict(r)
    estibas = estibas_del_recibo(r)
    solo = request.args.get("estiba", type=int)
    if solo:
        estibas = [e for e in estibas if e["numero"] == solo]
    return _render_rotulo(r, estibas)


@app.route("/rotulo/muestra")
def rotulo_muestra():
    """Rótulo de prueba (2 estibas) para revisar el tóner y que salga uno por hoja."""
    ahora = datetime.now().replace(microsecond=0)
    r = {"material": 12000444, "descripcion": "PRUEBA DE IMPRESION - NO PEGAR", "cajas_estiba": 80,
         "estibas_completas": 1, "saldo": 35, "vencimiento": (ahora.date() + timedelta(days=120)).isoformat(),
         "fecha_hora": ahora.isoformat(sep=" "), "ubicacion": "A1", "cuadrante": None, "vida_min": 60,
         "dias_vida_llegada": 120, "lote": "L0001", "oc": "4500000000", "auxiliar": "PRUEBA"}
    return _render_rotulo(r, estibas_del_recibo(r))


def _filtrar_recibos(con, args):
    condiciones, valores = ["1=1"], []
    if not args.get("anulados"):
        condiciones.append("anulado=0")
    if args.get("desde"):
        condiciones.append("fecha>=?"); valores.append(args["desde"])
    if args.get("hasta"):
        condiciones.append("fecha<=?"); valores.append(args["hasta"])
    if args.get("oc"):
        condiciones.append("oc=?"); valores.append(args["oc"].strip())
    if args.get("material"):
        tipo = normalizar_codigo(args["material"])
        if tipo and tipo[0] == "material":
            condiciones.append("material=?"); valores.append(tipo[1])
        else:
            condiciones.append("descripcion LIKE ?"); valores.append(f"%{args['material'].strip()}%")
    if args.get("auxiliar"):
        condiciones.append("auxiliar=?"); valores.append(args["auxiliar"])
    if args.get("status"):
        condiciones.append("status_entrada=?"); valores.append(args["status"])
    filas = con.execute(
        f"SELECT * FROM recibos WHERE {' AND '.join(condiciones)} ORDER BY id DESC LIMIT 2000", valores).fetchall()
    hoy = date.today()
    resultado = []
    for f in filas:
        f = dict(f)
        venc = _fecha(f["vencimiento"])
        f["dias_vida_hoy"] = (venc - hoy).days if venc else None
        if f["dias_vida_hoy"] is None:
            f["status_cedi"] = ""
        elif f["dias_vida_hoy"] < 0:
            f["status_cedi"] = "VENCIDO"
        elif f["vida_min"] and f["dias_vida_hoy"] < f["vida_min"]:
            f["status_cedi"] = "BAJO VIDA MÍN."
        else:
            f["status_cedi"] = "VIGENTE"
        f["total_estibas"] = f["estibas_completas"] + (1 if f["saldo"] >= 1 else 0)
        resultado.append(f)
    return resultado


@app.route("/consolidado")
def consolidado():
    args = request.args.to_dict()
    if not args:
        args = {"desde": date.today().isoformat(), "hasta": date.today().isoformat()}
    with db.conectar() as con:
        filas = _filtrar_recibos(con, args)
        personal = [r["nombre"] for r in con.execute("SELECT nombre FROM personal ORDER BY nombre")]
    totales = {
        "recibos": len(filas),
        "cajas": sum(f["cantidad"] for f in filas),
        "estibas": sum(f["total_estibas"] for f in filas),
        "no_cumple": sum(1 for f in filas if f["status_entrada"] == "NO CUMPLE"),
    }
    return render_template("consolidado.html", filas=filas, f=args, personal=personal, totales=totales,
                           pagina="consolidado")


@app.route("/consolidado/excel")
def consolidado_excel():
    with db.conectar() as con:
        filas = _filtrar_recibos(con, request.args.to_dict())
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Consolidado diario"
    columnas = [
        ("FECHA", "fecha_hora"), ("O.C", "oc"), ("MATERIAL", "material"), ("DESCRIPCION", "descripcion"),
        ("CANTIDAD CAJA", "cantidad"), ("F.VENCIMIENTO", "vencimiento"), ("LOTE", "lote"),
        ("AUX. RECIBO", "auxiliar"), ("Est. Completa", "estibas_completas"), ("Saldo cajas", "saldo"),
        ("Cajas x estiba", "cajas_estiba"), ("Días de vida Min para recibir", "vida_min"),
        ("Días de vida Útil llegada a Cava", "dias_vida_llegada"), ("Status Entrada", "status_entrada"),
        ("Días de vida Útil a la fecha", "dias_vida_hoy"), ("Status en CEDI", "status_cedi"),
        ("TTL ESTIBAS", "total_estibas"), ("CUADRANTE", "cuadrante"), ("Autorizado por", "autorizado_por"),
        ("Observación", "observacion"), ("Anulado", "anulado"),
    ]
    ws.append([c[0] for c in columnas])
    for f in filas:
        ws.append([f[c[1]] for c in columnas])
    ws.freeze_panes = "A2"
    salida = io.BytesIO()
    wb.save(salida)
    salida.seek(0)
    return send_file(salida, as_attachment=True, download_name=f"consolidado_{date.today().isoformat()}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/cruce", methods=["GET", "POST"])
def cruce():
    oc = (request.values.get("oc") or "").strip()
    sap_texto = request.form.get("sap", "")
    filas = []
    if oc:
        sap = {}
        for linea in sap_texto.splitlines():
            partes = linea.replace(";", "\t").replace(",", "\t").split("\t")
            partes = [p.strip() for p in partes if p.strip()]
            if len(partes) < 2:
                continue
            material, cantidad = a_entero(partes[0]), a_entero(partes[-1])
            if material and cantidad is not None:
                tipo = normalizar_codigo(str(material))
                material = tipo[1] if tipo and tipo[0] == "material" else material
                sap[material] = sap.get(material, 0) + cantidad
        with db.conectar() as con:
            contado = {r["material"]: dict(r) for r in con.execute(
                "SELECT material, MAX(descripcion) AS descripcion, SUM(cantidad) AS cantidad, COUNT(*) AS registros "
                "FROM recibos WHERE oc=? AND anulado=0 GROUP BY material", (oc,))}
            nombres = {r["material"]: r["descripcion"] for r in con.execute(
                f"SELECT material, descripcion FROM materiales WHERE material IN ({','.join('?' * len(sap))})",
                list(sap))} if sap else {}
        for material in sorted(set(sap) | set(contado)):
            c = contado.get(material, {})
            conteo = c.get("cantidad", 0)
            en_sap = sap.get(material, 0) if sap else None
            filas.append({
                "material": material,
                "descripcion": c.get("descripcion") or nombres.get(material, "(no está en el portafolio)"),
                "conteo": conteo, "registros": c.get("registros", 0), "sap": en_sap,
                "diferencia": conteo - en_sap if en_sap is not None else None,
            })
    return render_template("cruce.html", oc=oc, sap=sap_texto, filas=filas, pagina="cruce")


@app.route("/indicadores", methods=["GET", "POST"])
def indicadores():
    """Resultados del piloto para presentar a gerencia."""
    if request.method == "POST":
        minutos = request.form.get("minutos_excel", type=float)
        db.guardar_config("tiempo_excel_seg", str(int(minutos * 60)) if minutos and minutos > 0 else "")
        return redirect(url_for("indicadores", **request.args))
    hoy = date.today()
    desde = request.args.get("desde") or (hoy - timedelta(days=13)).isoformat()
    hasta = request.args.get("hasta") or hoy.isoformat()
    with db.conectar() as con:
        dias = [dict(r) for r in con.execute(
            """SELECT fecha, COUNT(*) AS recibos, SUM(cantidad) AS cajas,
                      SUM(estibas_completas + (saldo >= 1)) AS estibas,
                      AVG(tiempo_captura_seg) AS tiempo_prom,
                      SUM(status_entrada = 'NO CUMPLE') AS no_cumple,
                      COUNT(DISTINCT oc) AS ocs
               FROM recibos WHERE anulado = 0 AND fecha BETWEEN ? AND ?
               GROUP BY fecha ORDER BY fecha DESC""", (desde, hasta))]
        anulados = con.execute("SELECT COUNT(*) FROM recibos WHERE anulado=1 AND fecha BETWEEN ? AND ?",
                               (desde, hasta)).fetchone()[0]
        tiempo_app = con.execute(
            "SELECT AVG(tiempo_captura_seg) FROM recibos WHERE anulado=0 AND fecha BETWEEN ? AND ?",
            (desde, hasta)).fetchone()[0]
        materiales = con.execute("SELECT COUNT(*) FROM materiales WHERE date(actualizado) BETWEEN ? AND ?",
                                 (desde, hasta)).fetchone()[0]
    tiempo_excel = a_entero(db.leer_config("tiempo_excel_seg"))
    recibos = sum(d["recibos"] for d in dias)
    resumen = {
        "recibos": recibos,
        "cajas": sum(d["cajas"] or 0 for d in dias),
        "estibas": sum(d["estibas"] or 0 for d in dias),
        "no_cumple": sum(d["no_cumple"] or 0 for d in dias),
        "anulados": anulados,
        "materiales": materiales,
        "tiempo_app": tiempo_app,
        "tiempo_excel": tiempo_excel,
        "dias": len(dias),
    }
    if tiempo_app and tiempo_excel and dias:
        ahorro_recibo = tiempo_excel - tiempo_app
        recibos_dia = recibos / len(dias)
        resumen["ahorro_recibo"] = ahorro_recibo
        resumen["ahorro_pct"] = ahorro_recibo / tiempo_excel * 100
        resumen["horas_mes"] = ahorro_recibo * recibos_dia * DIAS_HABILES_MES / 3600
    return render_template("indicadores.html", dias=dias, r=resumen, desde=desde, hasta=hasta,
                           pagina="indicadores")


@app.route("/portafolio")
def portafolio():
    q = (request.args.get("q") or "").strip()
    with db.conectar() as con:
        if q:
            tipo = normalizar_codigo(q)
            if tipo and tipo[0] == "material":
                filas = con.execute("SELECT * FROM materiales WHERE material=? OR CAST(material AS TEXT) LIKE ?",
                                    (tipo[1], f"%{q}")).fetchall()
            else:
                filas = con.execute("SELECT * FROM materiales WHERE descripcion LIKE ? OR ean=? ORDER BY descripcion",
                                    (f"%{q}%", q)).fetchall()
        else:
            filas = con.execute("SELECT * FROM materiales ORDER BY descripcion").fetchall()
        filas = [dict(f) for f in filas]
        total = con.execute("SELECT COUNT(*) FROM materiales").fetchone()[0]
    return render_template("portafolio.html", filas=filas, q=q, total=total, pagina="portafolio",
                           mensaje=request.args.get("mensaje"))


@app.route("/portafolio/importar", methods=["POST"])
def portafolio_importar():
    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename:
        return redirect(url_for("portafolio", mensaje="Seleccione un archivo de Excel"))
    try:
        wb = openpyxl.load_workbook(archivo, data_only=True, read_only=True)
        ws = importar_excel._hoja(wb, "PORTAFOLIO") or wb.worksheets[0]
        materiales = importar_excel.leer_portafolio(ws)
        with db.conectar() as con:
            n = importar_excel.guardar_materiales(con, materiales, sobrescribir=True)
    except Exception as e:  # archivo dañado o sin las columnas esperadas
        return redirect(url_for("portafolio", mensaje=f"No se pudo importar: {e}"))
    return redirect(url_for("portafolio", mensaje=f"Se cargaron o actualizaron {n} materiales"))


@app.route("/personal", methods=["GET", "POST"])
def personal():
    with db.conectar() as con:
        if request.method == "POST":
            nombre = " ".join((request.form.get("nombre") or "").upper().split())
            accion = request.form.get("accion")
            if accion == "agregar" and nombre:
                con.execute("INSERT INTO personal (nombre) VALUES (?) ON CONFLICT(nombre) DO UPDATE SET activo=1",
                            (nombre,))
            elif accion in ("activar", "desactivar"):
                con.execute("UPDATE personal SET activo=? WHERE id=?",
                            (1 if accion == "activar" else 0, request.form.get("id", type=int)))
            return redirect(url_for("personal"))
        filas = con.execute("SELECT * FROM personal ORDER BY activo DESC, nombre").fetchall()
    return render_template("personal.html", filas=filas, pagina="personal")


def _es_este_pc():
    return request.remote_addr in ("127.0.0.1", "::1")


@app.route("/impresora", methods=["GET", "POST"])
def impresora_config():
    mensaje, error = request.args.get("mensaje"), None
    if request.method == "POST":
        accion = request.form.get("accion")
        if accion == "rotulo":
            tinta = request.form.get("tinta")
            db.guardar_config("rotulo_tinta", tinta if tinta in NIVELES_TINTA else "gris")
            tono = request.form.get("tono")
            db.guardar_config("rotulo_tono", tono if tono in TONOS_GRIS else "medio")
            db.guardar_config("rotulo_reverso_blanco", "1" if request.form.get("reverso") else "")
            return redirect(url_for("impresora_config", mensaje="Ajustes del rótulo guardados"))
        acciones = {
            "predeterminar": (impresora.predeterminar, "Ahora es la impresora predeterminada"),
            "una_cara": (impresora.una_cara, "Quedó en una cara y blanco y negro"),
            "preferencias": (impresora.abrir_preferencias, "Se abrió la ventana de preferencias en este PC"),
        }
        if accion in acciones:
            if not _es_este_pc():
                abort(403)
            funcion, texto = acciones[accion]
            nombre = request.form.get("nombre", "")
            try:
                funcion(nombre)
                return redirect(url_for("impresora_config", mensaje=f"{nombre}: {texto}"))
            except impresora.ErrorImpresora as e:
                error = str(e)
    impresoras = None
    if impresora.ES_WINDOWS and _es_este_pc():
        try:
            impresoras = impresora.listar()
        except (impresora.ErrorImpresora, ValueError) as e:
            error = error or f"No se pudo leer la lista de impresoras: {e}"
    return render_template("impresora.html", ajustes=ajustes_rotulo(), niveles=NIVELES_TINTA,
                           tonos=TONOS_GRIS,
                           impresoras=impresoras, es_windows=impresora.ES_WINDOWS, mensaje=mensaje, error=error,
                           pagina="impresora")


# ---------------------------------------------------------------- API

@app.get("/api/material/<codigo>")
def api_material(codigo):
    with db.conectar() as con:
        material, sugerido = buscar_material(con, codigo)
    if material:
        return jsonify({"encontrado": True, "material": material})
    return jsonify({"encontrado": False, "sugerido": sugerido}), 404


@app.post("/api/material")
def api_guardar_material():
    datos = request.get_json(force=True)
    material = a_entero(datos.get("material"))
    if not material or not (datos.get("descripcion") or "").strip():
        return jsonify({"error": "El material y la descripción son obligatorios"}), 400
    valores = {}
    for campo in CAMPOS_MATERIAL:
        v = datos.get(campo)
        valores[campo] = a_entero(v) if campo in CAMPOS_NUMERICOS else ((str(v).strip() or None) if v else None)
    valores["descripcion"] = valores["descripcion"].upper()
    if not valores["cajas_estiba"] and valores["tendidos"] and valores["pisos"]:
        valores["cajas_estiba"] = valores["tendidos"] * valores["pisos"]
    if not valores["cajas_estiba"]:
        return jsonify({"error": "Indique las cajas por estiba (o tendidos y pisos)"}), 400
    with db.conectar() as con:
        importar_excel.guardar_materiales(con, [{"material": material, **valores}], sobrescribir=True)
        fila = con.execute("SELECT * FROM materiales WHERE material=?", (material,)).fetchone()
    return jsonify({"material": dict(fila)})


@app.delete("/api/material/<int:material>")
def api_borrar_material(material):
    with db.conectar() as con:
        con.execute("DELETE FROM materiales WHERE material=?", (material,))
    return jsonify({"ok": True})


@app.post("/api/recibos")
def api_crear_recibo():
    d = request.get_json(force=True)
    errores = []
    with db.conectar() as con:
        material, _ = buscar_material(con, str(d.get("codigo", "")))
        if not material:
            errores.append("El material no está en el portafolio")
        cantidad = a_entero(d.get("cantidad"))
        if not cantidad or cantidad <= 0:
            errores.append("La cantidad debe ser mayor que cero")
        vencimiento = _fecha(d.get("vencimiento"))
        if not vencimiento:
            errores.append("Falta la fecha de vencimiento")
        oc = "".join(ch for ch in str(d.get("oc", "")) if ch.isdigit())
        if not oc:
            errores.append("Falta el número de orden de compra")
        auxiliar = (d.get("auxiliar") or "").strip()
        if not auxiliar:
            errores.append("Seleccione el auxiliar de recibo")
        patron = a_entero(d.get("patron"))
        cajas_estiba = patron or (material or {}).get("cajas_estiba")
        if material and not cajas_estiba:
            errores.append("El material no tiene cajas por estiba en el portafolio; digite el patrón de estibado")
        if errores:
            return jsonify({"errores": errores}), 400

        calc = calcular(cantidad, cajas_estiba, vencimiento, material["vida_util_cedi"])
        autorizado = (d.get("autorizado_por") or "").strip()
        if calc["status"] == "NO CUMPLE" and not autorizado:
            return jsonify({"errores": ["El producto NO CUMPLE la vida útil mínima: se necesita quién autoriza"],
                            "requiere_autorizacion": True}), 409

        # Segundos desde que se empezó a digitar el código hasta guardar (indicador del piloto).
        tiempo = a_entero(d.get("tiempo_captura_seg"))
        tiempo = tiempo if tiempo and 0 < tiempo <= 1800 else None

        ahora = datetime.now().replace(microsecond=0)
        cur = con.execute(
            """INSERT INTO recibos (fecha_hora, fecha, oc, material, descripcion, cantidad, cajas_estiba, vencimiento,
                   lote, auxiliar, estibas_completas, saldo, vida_min, dias_vida_llegada, status_entrada, cuadrante,
                   ubicacion, autorizado_por, observacion, tiempo_captura_seg)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ahora.isoformat(sep=" "), ahora.date().isoformat(), oc, material["material"], material["descripcion"],
             cantidad, cajas_estiba, vencimiento.isoformat(), (d.get("lote") or "").strip().upper() or None,
             auxiliar, calc["estibas_completas"], calc["saldo"], material["vida_util_cedi"], calc["dias_vida"],
             calc["status"], material["cuadrante"], material["ubicacion"], autorizado or None,
             (d.get("observacion") or "").strip() or None, tiempo))
    return jsonify({"id": cur.lastrowid, **calc})


@app.post("/api/recibos/<int:recibo_id>/anular")
def api_anular_recibo(recibo_id):
    motivo = (request.get_json(silent=True) or {}).get("motivo", "").strip()
    with db.conectar() as con:
        con.execute("UPDATE recibos SET anulado=1, observacion=TRIM(COALESCE(observacion,'') || ' ANULADO: ' || ?) "
                    "WHERE id=?", (motivo, recibo_id))
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
