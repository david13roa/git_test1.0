# Diferencias de despacho de cava

Control de las diferencias de inventario de la **cava**: solo los cuadrantes
**CONGELADOS**, **NEVERA** y **FRUVER NEVERA**. Los demás cuadrantes se descartan
al leer el archivo, así que ningún número de este proyecto los incluye.

Responde tres preguntas: qué picker tiene diferencias en cada tienda, cuánto cuesta
exactamente, y quiénes son los que más pérdida generan.

Tres formas de usarlo, sobre el mismo análisis:

| | Para qué | Necesita instalar |
|---|---|---|
| **Servidor FastAPI** | Datos centralizados para todo el equipo, con API para otras herramientas. | Python en un equipo (el servidor). |
| **Tablero web** | Un archivo HTML que corre solo en el navegador. | Nada. |
| **Informe en Excel** | El libro que se archiva o se envía por correo. | Python. |

> **Por qué solo cava:** la comparación de cuadrantes es exacta, no por coincidencia
> parcial. `FRUVER` a secas **no** es cava y queda fuera; solo entra `FRUVER NEVERA`.
> Para analizar otros cuadrantes está la opción `--cuadrantes`, o `--todos-los-cuadrantes`.

---

## 1. Servidor FastAPI

Levanta la API y sirve el tablero desde un solo proceso.

### Arranque

En Windows, doble clic en **`EJECUTAR_SERVIDOR.bat`**: instala lo que falte, abre el
navegador y deja el servidor corriendo. Desde consola:

```bash
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

- Tablero: <http://localhost:8000>
- Documentación interactiva de la API: <http://localhost:8000/docs>

El Excel activo se guarda en `datos/activo.xlsx` y se recarga solo al reiniciar.
Para empezar, copie ahí el archivo de diferencias, o súbalo por la API.

### Endpoints

| Método y ruta | Qué devuelve |
|---|---|
| `GET /` | El tablero interactivo con los datos ya embebidos. |
| `GET /api/salud` | Si el servicio responde y si hay datos cargados. |
| `GET /api/meta` | Qué archivo está activo, qué periodo y qué cuadrantes cubre. |
| `GET /api/exclusiones` | Qué líneas se descartaron por error de captura y por qué. |
| `GET /api/filtros` | Pickers, tiendas, cuadrantes, estados y rango de fechas disponibles. |
| `GET /api/resumen` | Indicadores generales: costo, sobrantes, impacto neto, % atribuido. |
| `GET /api/pickers` | Ranking con costo por caja, % de entregas con diferencia y % acumulado. |
| `GET /api/picker-tienda` | Qué picker tiene diferencias en cada tienda y por cuánto. |
| `GET /api/tiendas` | Ranking de tiendas con el picker que más aporta en cada una. |
| `GET /api/materiales` | Materiales ordenados por costo de faltantes. |
| `GET /api/serie-diaria` | Costo por día de despacho. |
| `GET /api/detalle` | Diferencias línea a línea, paginadas. |
| `GET /api/datos` | El dataset comprimido que consume el tablero. |
| `GET /api/informe.xlsx` | Genera y descarga el informe completo en Excel. |
| `POST /api/cargar` | Reemplaza el dataset activo con un Excel nuevo. |

Todas las consultas aceptan los mismos filtros como parámetros:
`desde`, `hasta`, `estado`, `picker`, `tienda`, `cuadrante`, `buscar` y `soloCobertura`.

```bash
# Costo de un picker en el periodo donde sí hay datos de despacho
curl "http://localhost:8000/api/resumen?picker=URIBE&soloCobertura=true"

# Ranking de agosto en congelados
curl "http://localhost:8000/api/pickers?desde=2026-08-01&cuadrante=CONGELADOS"

# El informe en Excel de un rango
curl -o informe.xlsx "http://localhost:8000/api/informe.xlsx?desde=2026-08-19"

# Cargar el archivo del mes nuevo
curl -X POST -F "archivo=@INFORME_DIFERENCIAS.xlsx" http://localhost:8000/api/cargar
```

Si el archivo que se sube no sirve, **el que estaba en uso no se toca**: se valida
completo antes de reemplazarlo.

### Estructura

| Archivo | Qué hace |
|---|---|
| `backend/main.py` | Rutas de la API y entrega del tablero. |
| `backend/almacen.py` | Dataset activo en memoria, persistencia y filtros. |
| `backend/consultas.py` | Las agregaciones que responde cada endpoint. |

---

## 2. Tablero web

Un solo archivo `.html` que corre **completamente en el navegador**: no hay servidor,
no hay instalación y los datos nunca salen del equipo de quien lo abre. Funciona
publicado en una URL o abierto desde el disco con doble clic.

### Qué trae

| Pestaña | Para qué sirve |
|---|---|
| **Panorama** | Costo total, tendencia diaria, faltantes contra sobrantes y el ranking de pickers. |
| **Pickers** | Tabla completa con costo por caja y % de entregas con diferencia, más la matriz picker × tienda. |
| **Tiendas** | Ranking de tiendas y el picker que más aporta al costo en cada una. |
| **Materiales** | Las referencias que más se pierden. |
| **Detalle** | Línea a línea, filtrable y exportable. |

El aviso del inicio declara las líneas excluidas por error de captura y permite
desplegar cuáles fueron.

Los filtros de arriba (fechas, estado, picker, tienda, cuadrante, búsqueda de material)
afectan todas las pestañas a la vez. Al hacer clic en una barra o en una fila se filtra
el tablero por ese picker o esa tienda. El botón **Exportar CSV** baja lo que esté
en pantalla, y **Cargar Excel** procesa un archivo nuevo sin salir de la página.

### Versión sin datos (para publicar)

```bash
python tablero/construir.py --vacio -o index.html
```

Produce el tablero **sin ningún dato**: quien lo abre carga su propio Excel, que se
procesa en su navegador y no sale del equipo. Es la versión apta para publicar en un
sitio público, porque el archivo no contiene información de la empresa. Pesa 76 KB.

La casilla «recordar los datos en este navegador» guarda el análisis en el equipo de
quien lo usa para no volver a cargar el archivo cada vez; viene desactivada y el botón
«Olvidar datos» lo borra.

### Regenerarlo con datos nuevos

```bash
pip install -r requirements.txt
python tablero/construir.py --excel INFORME_DIFERENCIAS.xlsx -o tablero_diferencias.html
```

Eso produce el `.html` listo para publicar o enviar. También se puede hacer en dos pasos
si se quiere guardar el JSON intermedio:

```bash
python preparar_datos_web.py INFORME_DIFERENCIAS.xlsx -o datos.json
python tablero/construir.py datos.json -o tablero_diferencias.html
```

Para el mes a mes no hace falta regenerar nada: basta abrir el tablero y usar
**Cargar Excel** con el archivo nuevo.

### Archivos

| Archivo | Qué hace |
|---|---|
| `tablero/plantilla.html` | El tablero: estilos, gráficos en SVG y toda la lógica. Los datos entran donde dice `/*__DATOS__*/`. |
| `tablero/construir.py` | Inserta los datos en la plantilla y produce el archivo final. |
| `preparar_datos_web.py` | Convierte el Excel en el JSON compacto que consume el tablero. |

Los gráficos están dibujados a mano en SVG, sin librerías de terceros, justamente para
que el tablero funcione sin internet. La única dependencia externa es la tipografía y el
lector de Excel del botón «Cargar Excel», y ambos degradan sin romper nada.

---

## 3. Informe en Excel

Programa en Python que toma el archivo `INFORME_DIFERENCIAS.xlsx` y genera un
informe en Excel con siete hojas.

### Instalación en el computador de la empresa (Windows)

Necesitas 3 archivos en una misma carpeta: `informe_diferencias.py`,
`requirements.txt` y `EJECUTAR_INFORME.bat`.

**1. Instalar Python** (una sola vez). Descárgalo de
<https://www.python.org/downloads/> y, en la primera pantalla del instalador,
**marca la casilla "Add Python to PATH"** antes de darle a instalar. Ese paso es
el que suele fallar; sin él, el programa no encuentra Python.

> Si el equipo tiene restricciones de administrador, elige la opción
> *"Install for me only"* / *"Solo para mí"*: no requiere permisos de admin.

**2. Poner los 3 archivos en una carpeta** junto con el Excel
`INFORME_DIFERENCIAS.xlsx`.

**3. Doble clic en `EJECUTAR_INFORME.bat`.** La primera vez instala solo las
librerías que faltan (tarda un minuto); después ya corre directo. Se abre una
ventana negra con el resumen y el ranking, y el Excel del informe queda en la
misma carpeta como `INFORME_PICKERS_INFORME_DIFERENCIAS.xlsx`.

También puedes **arrastrar cualquier Excel encima del `.bat`** para procesar ese
archivo en particular.

### Si la red de la empresa bloquea la instalación

Es lo más común en equipos corporativos: el `pip install` falla por el proxy. Abre
el *Símbolo del sistema* (`cmd`) y prueba:

```
py -m pip install --user pandas openpyxl
```

Si sigue fallando, pídele a sistemas que instale esas dos librerías, o descarga los
archivos `.whl` de `pandas` y `openpyxl` desde <https://pypi.org> en un equipo con
internet e instálalos con `py -m pip install --user ruta\al\archivo.whl`.

### Uso desde la consola

Si prefieres la línea de comandos (Windows, Mac o Linux):

```bash
pip install -r requirements.txt
```

```bash
# Informe estándar (solo diferencias con ESTADO = "Aplica")
python informe_diferencias.py INFORME_DIFERENCIAS.xlsx

# Elegir el nombre del archivo de salida
python informe_diferencias.py INFORME_DIFERENCIAS.xlsx -o informe_agosto.xlsx

# Comparar pickers solo en el periodo y los cuadrantes que cubre la hoja de despachos
python informe_diferencias.py INFORME_DIFERENCIAS.xlsx --solo-cobertura

# Un rango de fechas puntual, incluyendo todos los estados
python informe_diferencias.py INFORME_DIFERENCIAS.xlsx --estado todos --desde 2026-08-01 --hasta 2026-08-31
```

Si no se indica `-o`, el resultado se guarda como `INFORME_PICKERS_<archivo>.xlsx`
junto al archivo de entrada. Además, el resumen y el ranking se imprimen en la
consola.

Si ejecutas `python informe_diferencias.py` **sin indicar el archivo**, el programa
busca el Excel en su propia carpeta; si hay varios, te pregunta cuál usar.

### Opciones

| Opción | Descripción |
|---|---|
| `-o, --salida` | Ruta del Excel de salida. |
| `--hoja-diferencias` | Hoja con las diferencias (nombre o índice). Por defecto `Hoja1`. |
| `--hoja-despachos` | Hoja con los despachos y el picker. Por defecto `Hoja2`. |
| `--estado` | `aplica` (por defecto), `sin-pendientes` o `todos`. |
| `--metrica` | Criterio del ranking: `faltante` (por defecto), `neto` o `absoluto`. |
| `--cuadrantes` | Cuadrantes a analizar, separados por coma. Por defecto los de cava. |
| `--todos-los-cuadrantes` | Analiza todos los cuadrantes, sin el recorte de cava. |
| `--sin-exclusiones` | Ignora `exclusiones.json` y analiza los datos crudos. |
| `--solo-cobertura` | Limita el análisis al periodo y los cuadrantes que cubre la hoja de despachos. |
| `--desde`, `--hasta` | Rango de fechas `AAAA-MM-DD`. |
| `--top` | Cuántos pickers mostrar en consola (por defecto 15). |

---

## Líneas excluidas por error de captura

Algunas líneas del Excel son errores de digitación que distorsionan todo el análisis.
En vez de filtrarlas con un umbral automático —que el mes siguiente descartaría datos
buenos sin avisar— se declaran una por una en **`exclusiones.json`**, con su motivo y
quién lo autorizó.

```json
{
  "exclusiones": [
    {
      "entrega": "9832115290",
      "material": 12000395,
      "unidades": -127453,
      "motivo": "Cantidad imposible: 127.453 unidades de pizza de 130 g en una sola entrega...",
      "reportadoPor": "David Roa",
      "registradoEl": "2026-09-01"
    }
  ]
}
```

Una regla saca solo las líneas que coinciden con **todos** los campos que declara, así
que entre más campos, más estrecha. Los criterios disponibles son `entrega`, `material`,
`unidades`, `tienda`, `ceco` y `fecha` (la fecha de la línea). Los campos `motivo`,
`reportadoPor` y `registradoEl` son notas y no se usan para comparar.

**Nada se descarta en silencio.** Lo excluido aparece en la hoja `Excluidas` del Excel,
en `GET /api/exclusiones`, y en un aviso desplegable al inicio del tablero. Para ver los
datos crudos: `python informe_diferencias.py archivo.xlsx --sin-exclusiones`.

### Efecto de la exclusión actual

Una sola línea —127.453 unidades de pizza de 130 g en FELICIDAD el 13 de agosto—
valía $675.500.900, el 53 % de todo el costo de la cava. La siguiente línea más
costosa del periodo es 330 veces menor ($2.051.082).

| | Con la línea | Sin la línea |
|---|---|---|
| Costo de faltantes | $1.278.044.658 | **$602.543.758** |
| Tienda #1 | FELICIDAD (53,3 % del total) | ARRECIFE (2,3 %) |
| Tendencia diaria | plana con un pico | legible |

El ranking de pickers no cambia: esa línea no tenía picker asignado.

---

## Cómo se asigna el picker a cada diferencia

_Aplica igual al tablero y al informe de Excel._

La hoja de diferencias no trae el número de entrega en una columna propia: viene
dentro de la llave concatenada (`COMPROBACIÓN DUPLICADOS`), con el formato
`CECO(10 caracteres) + N° ENTREGA(10 dígitos) + CÓDIGO MATERIAL(8 dígitos) + UNIDADES`.

El programa extrae ese número de entrega y lo cruza contra la hoja de despachos,
que sí indica el picker responsable de cada entrega. **No se cruza por nombre de
tienda**, porque las dos hojas usan nomenclaturas distintas (`BELEN` vs
`BOG BELÉN`, `AV ROJAS` vs `AV ROJAS II`); el número de entrega es la única llave
confiable.

Las diferencias cuya entrega no aparece en la hoja de despachos quedan en la hoja
`Sin Picker`, para que ningún peso se pierda del total.

### Hojas del informe

| Hoja | Contenido |
|---|---|
| **Resumen** | Indicadores generales: periodo, costo de faltantes, sobrantes, impacto neto y qué porcentaje del costo se pudo atribuir a un picker. |
| **Ranking Pickers** | Ranking por costo, con líneas, tiendas y entregas afectadas, unidades, valores, `% del costo total` y `% acumulado` (para leerlo tipo Pareto). Incluye un gráfico del top 10. |
| **Picker x Tienda** | El cruce que responde "qué picker tiene diferencias en cada tienda" y por cuánto exactamente. |
| **Detalle** | Línea a línea: fecha, picker, tienda, entrega, ruta, material, unidades, precio unitario, valor, causal y responsables comerciales. |
| **Ranking Tiendas** | Tiendas ordenadas por impacto, con el picker que más aporta en cada una. |
| **Top Materiales** | Los 100 materiales con mayor valor de faltantes. |
| **Sin Picker** | Diferencias que no se pudieron atribuir. |
| **Excluidas** | Líneas descartadas por error de captura, con su motivo. |

## Definición de las métricas

- **VALOR FALTANTES** — suma de los valores negativos, en positivo. Es el costo real.
- **VALOR SOBRANTES** — suma de los valores positivos.
- **IMPACTO NETO** — sobrantes menos faltantes (lo que efectivamente se perdió).
- **IMPACTO ABSOLUTO** — faltantes más sobrantes; mide el descontrol total, porque un
  sobrante también es un error de picking aunque no cueste plata.
- **% ENTREGAS CON DIFERENCIA** — entregas del picker con alguna diferencia sobre el
  total que despachó. Normaliza el ranking: un picker con muchas entregas puede tener
  más diferencias sin ser peor.
- **COSTO POR CAJA** y **COSTO POR ENTREGA DESPACHADA** — costo de faltantes dividido
  por el volumen que movió el picker. Son los indicadores justos para comparar entre
  personas con cargas de trabajo distintas.

## Cobertura de los datos

En el archivo de ejemplo, las diferencias de cava abarcan del **1 de julio al 28 de
agosto**, mientras que la hoja de despachos solo cubre del **19 al 31 de agosto** y
los cuadrantes **CONGELADOS** y **NEVERA**. Por eso solo se puede asignar picker a
una parte de las diferencias: 14,2 % de las líneas, que son $74,8 millones de los
$602,5 millones de faltantes (después de la exclusión documentada más abajo).

Con `--solo-cobertura` el análisis se limita a esa ventana, y ahí la atribución sube
a más de la mitad de las líneas. Para atribuir el resto del periodo hay que ampliar
la hoja de despachos con las entregas de los demás días y cuadrantes; el programa las
tomará automáticamente sin cambios en el código.

### Solución de problemas

| Mensaje | Qué hacer |
|---|---|
| `no se encontro Python en este equipo` | Reinstala Python marcando **"Add Python to PATH"**. |
| `No se pudieron instalar las librerias` | Es el proxy de la empresa. Ver la sección de instalación arriba. |
| `No se encontro ningun Excel en la carpeta` | Copia el Excel junto al programa, o arrástralo sobre el `.bat`. |
| `Permission denied` al guardar | Cierra el Excel del informe anterior; Windows lo bloquea mientras está abierto. |
| `No se encontro ninguna columna para...` | Cambiaron los encabezados del Excel. El mensaje lista las columnas que sí encontró. |

### Notas de robustez

- Los encabezados se detectan solos (la hoja de diferencias tiene un título en la
  primera fila), y las columnas se buscan sin distinguir tildes, mayúsculas ni saltos
  de línea, así que sirve aunque cambien detalles del formato.
- Los precios y unidades se convierten tolerando `$`, puntos de miles y comas.
- Si `$ TOTAL` viene vacío, se recalcula como `precio unitario x unidades`.
- Los nombres de picker se normalizan (espacios sobrantes y mayúsculas), de modo que
  `QUEVEDO ` y `QUEVEDO` cuentan como la misma persona.
