// Pantalla de recibo: replica los cálculos de la hoja "ROTULO RECIBO FEFO-FIFO".
const $ = (id) => document.getElementById(id);
const campos = ["codigo", "cantidad", "vencimiento", "patron", "lote", "auxiliar"];
let material = null;   // material encontrado en el portafolio
let sugerido = null;   // datos del maestro SAP cuando el material no está en el portafolio
let inicioCaptura = null;  // para medir cuánto tarda cada recibo (indicador del piloto)

const guardarPreferencia = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
const leerPreferencia = (k) => { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } };

function aviso(texto, esError = false) {
  const el = $("aviso");
  el.innerHTML = texto;
  el.classList.toggle("error", esError);
  el.hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function fechaLocal(iso) {
  if (!iso) return null;
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d);
}

function formatoFecha(iso) {
  if (!iso) return "dd-mm-aaaa";
  const [a, m, d] = iso.split("-");
  return `${d}-${m}-${a}`;
}

function calcular() {
  const cantidad = Number($("cantidad").value) || 0;
  const cajas = Number($("patron").value) || (material && material.cajas_estiba) || 0;
  const completas = cajas ? Math.floor(cantidad / cajas) : 0;
  const saldo = cajas ? cantidad - completas * cajas : 0;
  const venc = fechaLocal($("vencimiento").value);
  const hoy = new Date(); hoy.setHours(0, 0, 0, 0);
  const dias = venc ? Math.round((venc - hoy) / 86400000) : null;
  const vidaMin = material ? material.vida_util_cedi : null;
  let status = "—";
  if (material && !vidaMin) status = "SIN DATO DE VIDA ÚTIL";
  else if (material && dias !== null) status = dias < vidaMin ? "NO CUMPLE" : "CUMPLE";

  $("c-completas").textContent = material && cantidad ? completas : "—";
  $("c-cajas").textContent = cajas || "—";
  $("c-saldo-n").textContent = material && cantidad ? (saldo >= 1 ? 1 : 0) : "—";
  $("c-saldo").textContent = material && cantidad ? saldo : "—";
  $("c-vida-min").textContent = vidaMin ? `${vidaMin} días` : "—";
  $("c-dias").textContent = dias !== null ? `${dias} días` : "—";
  $("c-status-txt").textContent = status;
  $("c-status").className = "celda-calc status ancha " +
    (status === "CUMPLE" ? "cumple" : status === "NO CUMPLE" ? "no-cumple" : "");
  $("c-posicion").textContent = material ? (material.ubicacion || material.cuadrante || "—") : "—";
  $("c-total").textContent = material && cantidad ? completas + (saldo >= 1 ? 1 : 0) : "—";

  $("p-desc").textContent = material ? material.descripcion : " ";
  $("p-codigo").textContent = material ? String(material.material).slice(-4) : "----";
  $("p-cajas").textContent = cajas || 0;
  $("p-venc").textContent = formatoFecha($("vencimiento").value);
}

function mostrarMaterial() {
  const d = $("descripcion");
  if (material) {
    d.className = "descripcion-material";
    d.innerHTML = "";
    const t = document.createElement("span");
    t.textContent = `${material.material} · ${material.descripcion}`;
    const b = document.createElement("button");
    b.className = "boton chico"; b.type = "button"; b.textContent = "Editar";
    b.onclick = () => ModalMaterial.abrir({ ...material, _existente: true }, "Editar material", alGuardarMaterial);
    d.append(t, b);
  } else if (sugerido !== null) {
    d.className = "descripcion-material no-encontrado";
    d.innerHTML = "";
    const t = document.createElement("span");
    t.textContent = sugerido.descripcion
      ? `${sugerido.material} · ${sugerido.descripcion} — no está en el portafolio`
      : "El material no está en el portafolio";
    const b = document.createElement("button");
    b.className = "boton primario chico"; b.type = "button"; b.textContent = "+ Agregar al portafolio";
    b.onclick = () => ModalMaterial.abrir(sugerido, "Agregar material al portafolio", alGuardarMaterial);
    d.append(t, b);
  } else {
    d.className = "descripcion-material vacio";
    d.textContent = "Digite un código de material";
  }
  calcular();
}

function alGuardarMaterial(m) {
  material = m; sugerido = null;
  $("codigo").value = String(m.material);
  mostrarMaterial();
  $("cantidad").focus();
}

let ultimaBusqueda = "";
async function buscarMaterial() {
  const codigo = $("codigo").value.trim();
  if (codigo === ultimaBusqueda) return;
  ultimaBusqueda = codigo;
  material = null; sugerido = null;
  if (!/^\d+$/.test(codigo)) { mostrarMaterial(); return; }
  const r = await fetch(`/api/material/${codigo}`);
  if (codigo !== ultimaBusqueda) return;
  const res = await r.json();
  if (res.encontrado) material = res.material;
  else sugerido = res.sugerido || {};
  mostrarMaterial();
}

function limpiar() {
  for (const c of ["codigo", "cantidad", "vencimiento", "patron", "lote"]) $(c).value = "";
  material = null; sugerido = null; ultimaBusqueda = ""; inicioCaptura = null;
  mostrarMaterial();
  $("codigo").focus();
}

async function guardar(extra = {}) {
  await buscarMaterial();
  const datos = {
    oc: $("oc").value, codigo: $("codigo").value, cantidad: $("cantidad").value,
    vencimiento: $("vencimiento").value, patron: $("patron").value, lote: $("lote").value,
    auxiliar: $("auxiliar").value,
    tiempo_captura_seg: inicioCaptura ? Math.round((Date.now() - inicioCaptura) / 1000) : null, ...extra,
  };
  $("btn-guardar").disabled = true;
  try {
    const r = await fetch("/api/recibos", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos),
    });
    const res = await r.json();
    if (r.status === 409 && res.requiere_autorizacion) {
      const dias = $("c-dias").textContent, min = $("c-vida-min").textContent;
      $("autorizar-texto").textContent =
        `${material.descripcion}: le quedan ${dias} de vida y el mínimo para recibir es ${min}.`;
      $("modal-autorizar").showModal();
      $("autorizado_por").focus();
      return;
    }
    if (!r.ok) { aviso(res.errores.map((e) => `• ${e}`).join("<br>"), true); return; }
    imprimir(res.id);
    aviso(`✔ Recibo guardado: ${res.estibas_completas} estiba(s) completa(s)` +
      (res.saldo ? ` + 1 con saldo de ${res.saldo} cajas` : "") + ". Enviando rótulos a la impresora…");
    limpiar();
  } catch (e) {
    aviso("No hay conexión con el servidor. El recibo NO se guardó.", true);
  } finally {
    $("btn-guardar").disabled = false;
  }
}

function imprimir(id) {
  $("marco-impresion").src = `/rotulo/${id}?imprimir=1`;
}

// Cuando el rótulo termina de imprimirse se recarga para actualizar "Recibos de hoy".
window.addEventListener("message", (ev) => {
  if (ev.origin === location.origin && ev.data === "rotulo-impreso") location.reload();
});

// ---------- eventos
$("oc").value = leerPreferencia("recibo-bos-oc");
$("auxiliar").value = leerPreferencia("recibo-bos-auxiliar");
$("oc").addEventListener("change", () => guardarPreferencia("recibo-bos-oc", $("oc").value.trim()));
$("auxiliar").addEventListener("change", () => guardarPreferencia("recibo-bos-auxiliar", $("auxiliar").value));

let espera;
$("codigo").addEventListener("input", () => {
  if (!inicioCaptura) inicioCaptura = Date.now();
  clearTimeout(espera); espera = setTimeout(buscarMaterial, 250); });
for (const c of ["cantidad", "vencimiento", "patron"]) $(c).addEventListener("input", calcular);

campos.forEach((c, i) => {
  $(c).addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter" || ev.ctrlKey) return;
    ev.preventDefault();
    if (c === "codigo") buscarMaterial();
    const siguiente = campos[i + 1];
    (siguiente ? $(siguiente) : $("btn-guardar")).focus();
  });
});
$("oc").addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); $("codigo").focus(); } });
document.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && ev.ctrlKey && !document.querySelector("dialog[open]")) { ev.preventDefault(); guardar(); }
});

$("btn-guardar").addEventListener("click", () => guardar());
$("btn-limpiar").addEventListener("click", limpiar);
$("autorizar-cancelar").addEventListener("click", () => $("modal-autorizar").close());
$("form-autorizar").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const autorizado = $("autorizado_por").value.trim();
  if (!autorizado) return;
  $("modal-autorizar").close();
  guardar({ autorizado_por: autorizado, observacion: $("observacion").value });
  $("autorizado_por").value = ""; $("observacion").value = "";
});

mostrarMaterial();
