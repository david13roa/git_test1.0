# Informe de diferencias de despacho por picker

Programa en Python que toma el archivo `INFORME_DIFERENCIAS.xlsx` y genera un
informe en Excel donde se ve **qué picker tiene diferencias en cada tienda, el
valor exacto de cada una, y un ranking de quiénes generan más diferencias con el
costo que representan**.

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

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

## Cómo se asigna el picker a cada diferencia

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

## Hojas del informe

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

## Notas de robustez

- Los encabezados se detectan solos (la hoja de diferencias tiene un título en la
  primera fila), y las columnas se buscan sin distinguir tildes, mayúsculas ni saltos
  de línea, así que sirve aunque cambien detalles del formato.
- Los precios y unidades se convierten tolerando `$`, puntos de miles y comas.
- Si `$ TOTAL` viene vacío, se recalcula como `precio unitario x unidades`.
- Los nombres de picker se normalizan (espacios sobrantes y mayúsculas), de modo que
  `QUEVEDO ` y `QUEVEDO` cuentan como la misma persona.
