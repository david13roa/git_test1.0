# Diferencias de despacho por picker

Dos herramientas sobre el mismo análisis:

1. **Tablero web interactivo** — se abre con un link, no requiere instalar nada.
2. **Informe en Excel** — un programa de consola que genera el libro con todas las hojas.

Ambos responden lo mismo: qué picker tiene diferencias en cada tienda, el valor
exacto, y el ranking de quiénes generan más costo.

---

## 1. Tablero web

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

Los filtros de arriba (fechas, estado, picker, tienda, cuadrante, búsqueda de material)
afectan todas las pestañas a la vez. Al hacer clic en una barra o en una fila se filtra
el tablero por ese picker o esa tienda. El botón **Exportar CSV** baja lo que esté
en pantalla, y **Cargar Excel** procesa un archivo nuevo sin salir de la página.

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

## 2. Informe en Excel

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
| `--solo-cobertura` | Limita el análisis al periodo y los cuadrantes que cubre la hoja de despachos. |
| `--desde`, `--hasta` | Rango de fechas `AAAA-MM-DD`. |
| `--top` | Cuántos pickers mostrar en consola (por defecto 15). |

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

En el archivo de ejemplo, la hoja de diferencias abarca del **1 de julio al 28 de
agosto** y todos los cuadrantes, mientras que la hoja de despachos solo cubre del
**19 al 31 de agosto** y los cuadrantes **CONGELADOS** y **NEVERA**. Por eso solo se
puede asignar picker a una parte de las diferencias.

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
