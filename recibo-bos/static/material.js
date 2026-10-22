// Ventana para crear o editar un material del portafolio (se usa en Recibo y en Portafolio).
const ModalMaterial = (() => {
  const modal = document.getElementById("modal-material");
  const form = document.getElementById("form-material");
  const error = document.getElementById("modal-material-error");
  const campo = (n) => form.elements[n];
  let alGuardar = null;

  function recalcularCajas() {
    const t = Number(campo("tendidos").value), p = Number(campo("pisos").value);
    if (t > 0 && p > 0) campo("cajas_estiba").value = t * p;
  }
  campo("tendidos").addEventListener("input", recalcularCajas);
  campo("pisos").addEventListener("input", recalcularCajas);
  document.getElementById("m-cancelar").addEventListener("click", () => modal.close());

  function abrir(datos = {}, titulo = "Agregar material al portafolio", callback = null) {
    form.reset();
    error.hidden = true;
    for (const el of form.elements) {
      if (el.name && datos[el.name] != null) el.value = datos[el.name];
    }
    campo("material").readOnly = Boolean(datos.material && datos._existente);
    document.getElementById("modal-material-titulo").textContent = titulo;
    alGuardar = callback;
    modal.showModal();
    (datos.descripcion ? campo("tendidos") : campo("descripcion")).focus();
  }

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const datos = Object.fromEntries(new FormData(form));
    const r = await fetch("/api/material", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos),
    });
    const res = await r.json();
    if (!r.ok) {
      error.textContent = res.error || "No se pudo guardar";
      error.hidden = false;
      return;
    }
    modal.close();
    if (alGuardar) alGuardar(res.material);
  });

  return { abrir };
})();
