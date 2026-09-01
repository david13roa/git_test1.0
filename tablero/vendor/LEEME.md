# Dependencia incluida

`xlsx.full.min.js` es **SheetJS Community Edition 0.18.5**, licencia Apache-2.0
(el texto completo está en `LICENSE-xlsx.txt`).

Se incluye en el repositorio a propósito, en vez de cargarlo desde un CDN: en redes
corporativas los CDN suelen estar bloqueados, y sin este archivo el botón «Cargar
Excel» del tablero no funcionaría. Sirviéndolo desde el mismo sitio, el tablero no
depende de ningún servicio externo.

El tablero intenta primero esta copia local y solo recurre al CDN si no la encuentra,
de modo que también funciona cuando la página se publica sin la carpeta `vendor`.

Para actualizarlo:

    npm install xlsx@<version>
    cp node_modules/xlsx/dist/xlsx.full.min.js tablero/vendor/
    cp node_modules/xlsx/LICENSE tablero/vendor/LICENSE-xlsx.txt
