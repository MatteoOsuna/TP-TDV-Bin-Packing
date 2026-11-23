# TP2 — Armado de cargas para entregas de supermercado

Bin Packing con **similitud** y **temperatura**. Hay que repartir los productos del día en camiones de capacidad `C` usando pocos camiones, juntando productos parecidos y respetando la cadena de frío.

Función objetivo a minimizar:

```
alpha * K  -  beta * S
```

- `K`: cantidad de camiones.
- `S`: suma de las similitudes de los pares de productos que viajan en el mismo camión.

---

## 1. Requisitos

- **Compilador C++17**: `g++` (en Windows, MinGW) o CMake.
- **Python 3** con `matplotlib` y `networkx`. Solo hace falta para los gráficos, la ventana animada y los scripts de experimentos; el programa resuelve igual sin Python.

```bash
python -m pip install matplotlib networkx
```

## 2. Compilar

Desde la carpeta del proyecto:

```bash
g++ -std=c++17 -O2 -static -Isrc -o tp2.exe src/*.cpp
```

`-static` evita problemas con las bibliotecas de MinGW en Windows. También se puede compilar con CMake:

```bash
cmake -S . -B build
cmake --build build --config Release
```

> Si el compilador dice `Permission denied` al escribir `tp2.exe`, es porque el programa está abierto: cerralo y volvé a compilar.

## 3. Correr

Siempre desde la **carpeta del proyecto** (ahí busca `instancias/`, `resultados/` y los scripts).

### 3.1 Modo interactivo (para explorar)

```bash
./tp2.exe
```

Va preguntando:

1. **Heurística**: BFD, MOCHILA o COSTO (ver sección 6).
2. **Instancia**: lista todo lo que hay en `instancias/`, incluidas las subcarpetas.
3. **Temperatura**: sin restricción, Δ relativo, bandas fijas o híbrido (ver sección 6).
4. **Cómo ver la construcción**: ventana animada, texto en la consola o nada.

Para que las corridas se puedan comparar, el modo interactivo usa siempre los valores del modelo y no los pregunta: `alpha = 1`, `beta = 1/S_max` y `Δ = 6` grados. Se cambian en las constantes `ALPHA_FIJO` y `DELTA_FIJO` al principio de `src/main.cpp`. Para probar otros valores, usar el modo línea de comandos.

### 3.2 Modo línea de comandos (para experimentos y corrección)

```bash
./tp2.exe <input> <output> [metodo] [alpha] [beta] [delta] [modo]
```

| Parámetro | Valores | Por defecto |
|---|---|---|
| `input` | archivo de instancia | — |
| `output` | archivo donde se escribe la solución | — |
| `metodo` | `bfd`, `mochila`, `costo`, `meta` (y `ffd`, que solo queda como base) | `bfd` |
| `alpha` | número | `1` |
| `beta` | número, o `auto` = `1/S_max` | `auto` |
| `delta` | tolerancia de temperatura en grados | sin límite |
| `modo` | `delta`, `bandas`, `hibrido` | `delta` |

Ejemplos:

```bash
./tp2.exe instancias/ejemplo.txt resultados/salida.out
./tp2.exe instancias/inst_60.txt resultados/salida.out bfd 1 auto 6 delta
./tp2.exe instancias/inst_60.txt resultados/salida.out bfd 1 1 6 delta
```

Imprime un resumen: `Metodo: bfd | modo: delta | K = 5 | objetivo = 4.50988`.

## 4. Ver los resultados

Cada corrida del modo interactivo crea su propia carpeta, con la fecha y la hora en que se corrió, y guarda ahí sus tres archivos:

```
resultados/
  solucion_2026-11-20_15-04-03/
    BFD_inst_n40_s3.out
    BFD_inst_n40_s3.png
    BFD_inst_n40_s3.traza
  solucion_2026-11-20_15-04-05/
    MOCHILA_inst_n40_s3.out
    ...
```

| Archivo | Qué es |
|---|---|
| `<HEURISTICA>_<instancia>.out` | la solución: una línea por camión con los índices (desde 0) de sus productos |
| `<HEURISTICA>_<instancia>.png` | gráfico de la solución: una barra por camión, capacidad y rango de temperatura de cada camión |
| `<HEURISTICA>_<instancia>.traza` | los pasos de la construcción (lo usa la ventana animada) |

Al terminar, el programa muestra en qué carpeta quedó todo. Si dos corridas caen en el mismo segundo, la segunda agrega `_2` al nombre para no pisar la anterior.

### Ventana animada

Muestra cómo la heurística arma la solución, paso a paso:

- **Izquierda**: el grafo de similitud. Cada punto es un producto (más grande = más pesado) y los productos parecidos quedan juntos. Gris = sin ubicar, color = camión asignado, aro dorado = producto del paso actual.
- **Derecha**: los camiones y el **vecindario** del paso: con borde negro los camiones donde el producto entra, apagados los que no, y en dorado el producto recién cargado.
- **Abajo**: el paso, la decisión que tomó la heurística y la solución parcial (camiones y similitud).

Controles: botones o teclado (espacio = play/pausa, flechas = paso a paso, Inicio/Fin). La barra cambia la velocidad.

Para guardar una captura de un paso (por ejemplo, para el informe):

```bash
python experimentacion/ver_construccion.py --inst instancias/lote_dificil/inst_n40_s3.txt --traza resultados/solucion_2026-11-20_15-04-03/BFD_inst_n40_s3.traza --heuristica BFD --guardar captura.png --paso 10
```

## 5. Experimentos

### Batería completa desde la terminal

Para comparar heurísticas, modelos térmicos, META y soluciones exactas pequeñas:

```powershell
py -3 experimentacion/ejecutar_suite.py
```

El script compila `tp2.exe` si falta o está desactualizado y genera (si faltan)
instancias sintéticas con `n = 100, 250, 500, 1000`, cinco semillas y capacidades
`C = 20, 100`. Después corre:

- FFD, BFD, MOCHILA y COSTO bajo `delta`, `bandas` e `hibrido`;
- un barrido de `delta = 2, 4, 6, 8, 12` sobre instancias representativas:
  `delta=2` usa el perfil por categorías y los demás, temperaturas de frontera;
- META con una configuración fija de 100 iteraciones y tres semillas, en
  cuatro casos pequeños. No barre hiperparámetros;
- una comparación contra un óptimo exacto por programación dinámica para tres
  instancias pequeñas (`n=10`, `C=20`).

Guarda todas las corridas en un único CSV dentro de una carpeta nueva de
`resultados/`. Las métricas incluyen `K`, cota y gap, similitud absoluta y
normalizada, objetivo, utilización, factibilidad y tiempo. En la fase exacta
también aparecen `K_optimo` y `delta_objetivo_optimo`. El resumen de terminal
informa media y desvío de `K` y `S_norm`, mediana de tiempo y resultados por
tamaño/capacidad. La ejecución predeterminada realiza 723 corridas; la
comparación META se puede omitir con `--sin-meta-tuning`. Usa `alpha=1` y
`beta=auto` (`1/S_max`); no vuelve a barrer esos parámetros.

El barrido térmico y la comparación META pueden omitirse para una corrida más
corta:

```powershell
py -3 experimentacion/ejecutar_suite.py --sin-barrido-temperatura --sin-meta-tuning
```

También se pueden reducir tamaños y semillas. Por ejemplo, prueba breve:

```powershell
py -3 experimentacion/ejecutar_suite.py --sizes 20 --seeds 1 --capacities 100 --sin-meta-tuning --sin-barrido-temperatura
```

El barrido alpha/beta y su justificación forman parte del informe final:
`report/informe_actualizado.docx`. El CSV crudo y el gráfico del barrido se
conservan en `report/` como respaldo experimental.

Las instancias generadas son sintéticas y permiten comparaciones controladas; no
deben presentarse como datos reales de Todiafour. El perfil de frontera se guarda
separado en `instancias/suite_fronteras/`, sin reemplazar las instancias existentes.
Las herramientas de experimentos individuales se describen debajo.

| Script | Qué hace | Comando |
|---|---|---|
| `generador/generador.py` | crea una instancia; `--perfil-temperatura fronteras` genera temperaturas cercanas a cambios entre modelos | `python generador/generador.py --n 50 --C 100 --seed 1 --out instancias/inst_50.txt` |
| `experimentacion/comparar_lote.py` | corre las heurísticas sobre una carpeta de instancias y compara K, gap contra la cota inferior, similitud y tiempo (CSV + gráfico) | `python experimentacion/comparar_lote.py --instdir instancias/lote` |
| `experimentacion/comparar_constructivas.py` | BFD, MOCHILA y COSTO lado a lado sobre una instancia, con K, similitud y objetivo de cada una (marca la de mejor objetivo). Con `--metodos` se eligen otras | `python experimentacion/comparar_constructivas.py --inst instancias/lote_dificil/inst_n40_s3.txt --delta 6` |
| `experimentacion/comparar_temperatura.py` | camiones que cuesta cada modelo de temperatura, variando Δ | `python experimentacion/comparar_temperatura.py --instdir instancias/lote` |
| `experimentacion/graficar_grafo.py` | la solución dibujada como grafo | `python experimentacion/graficar_grafo.py --inst instancias/inst_25.txt --metodo costo` |

Todos aceptan `--alpha`, `--beta`, `--delta` y `--modo` (salvo `comparar_temperatura.py`, que barre Δ solo). `comparar_lote.py` compara BFD, MOCHILA y COSTO; con `--metodos` se eligen otras (por ejemplo `--metodos ffd,bfd`).

Cada corrida de un script crea su propia carpeta en `resultados/`, con la fecha y la hora, y guarda ahí sus archivos junto con un `parametros.txt` que anota con qué se corrió:

| Script | Carpeta | Archivos |
|---|---|---|
| `comparar_lote.py` | `comparacion_lote_<fecha_hora>/` | `comparacion_lote.csv`, `comparacion_lote.png` |
| `comparar_constructivas.py` | `comparacion_constructivas_<fecha_hora>/` | `comparacion_<instancia>.png` |
| `comparar_temperatura.py` | `comparacion_temperatura_<fecha_hora>/` | `comparacion_temperatura.png`, `k_medio_por_modelo.csv` |
| `graficar_grafo.py` | `grafo_<fecha_hora>/` | `<HEURISTICA>_<instancia>.png` |

Si se pasa `--out` (o `--csv`) a mano, el script guarda en esa ruta y no crea la carpeta con fecha. La función que arma las carpetas está en `experimentacion/carpetas.py`.

> El **gap** de `comparar_lote.py` usa la cota inferior `L = ⌈Σw / C⌉`, que solo mira el peso. Con restricción de temperatura hacen falta más camiones que eso, así que el gap sale alto aunque la solución sea buena: sirve para comparar heurísticas entre sí, no como distancia al óptimo.

**Instancias incluidas** (`instancias/`):

- `ejemplo.txt`: la del enunciado.
- `inst_25.txt`, `inst_40.txt`, `inst_60.txt`: sueltas, para probar y graficar.
- `lote/`: 24 instancias "fáciles" (n de 10 a 100, 3 semillas cada una, C = 100).
- `lote_dificil/`: las mismas 24 con C = 20 (productos grandes respecto de la capacidad).

Para regenerar un lote:

```bash
for n in 10 20 30 40 50 60 80 100; do for s in 1 2 3; do python generador/generador.py --n $n --C 100 --seed $s --out instancias/lote/inst_n${n}_s${s}.txt; done; done
```

## 6. Modelo elegido

**Alpha y beta.** Se usa `alpha = 1` y `beta = 1 / S_max`, donde `S_max` es la suma de todas las similitudes de la instancia. El objetivo queda `K - S/S_max`: la similitud normalizada aporta como máximo una unidad, por lo que no puede compensar una diferencia de dos o más camiones; en el caso extremo puede empatar una diferencia de un camión. La justificación completa, el barrido realizado y los resultados están en `report/informe_actualizado.docx`; los datos crudos y el gráfico están en `report/`.

**Temperatura: restricción dura, con Δ = 6 grados.** Un camión no puede mezclar temperaturas incompatibles. En el perfil normal, los productos de una misma categoría difieren como mucho 4 grados (±2 alrededor de su temperatura típica) y dos categorías de distinta temperatura están a 12 grados o más. Cualquier Δ entre 4 y 12 deja cada categoría junta sin mezclarla con otra; elegimos Δ = 6 por estar dentro de ese rango con margen. El perfil `fronteras` existe para el barrido experimental: usa temperaturas cerca de los umbrales, de modo que delta, bandas e híbrido puedan producir resultados distintos. Usamos el mismo Δ en los modos delta e híbrido para que la comparación entre ellos sea justa. Hay tres formas de aplicar la restricción:

| Modo | Regla para cada camión |
|---|---|
| `delta` | temperatura más alta − temperatura más baja ≤ Δ |
| `bandas` | todos los productos en la misma categoría (congelado, refrigerado, ambiente, caliente) |
| `hibrido` | hay una temperatura fija de heladera (−18, 4, 20 o 65) a ≤ Δ de todos los productos |

**Heurísticas constructivas.** Tres formas distintas de armar la solución:

| Heurística | Cómo arma la solución | Qué prioriza |
|---|---|---|
| **BFD** | de mayor a menor peso, cada producto al camión **más lleno** donde entra | no dejar huecos, producto por producto |
| **MOCHILA** | **un camión por vez**: arranca por el producto más pesado que queda y lo completa con el grupo de productos que más lo llena (problema de la mochila) | camiones lo más llenos posible |
| **COSTO** | de mayor a menor peso, cada producto al camión donde **menos empeora la función objetivo** | lo que mide la nota (con nuestros α y β: la similitud) |

MOCHILA arranca cada camión por el producto más pesado porque los productos chicos se acomodan fácil en cualquier camión y los pesados no: conviene ubicarlos primero. Llenar el camión "golosamente" (del más pesado al más liviano mientras entren) daría exactamente lo mismo que FFD; la mochila es lo que la hace distinta.

FFD (primer camión donde entra) quedó afuera porque es casi igual a BFD: en los experimentos sobre 48 instancias dieron, en promedio, la misma cantidad de camiones.

## 7. Formato de archivos

**Entrada** (`instancias/*.txt`):

```
n C
w_0 t_0
...
w_{n-1} t_{n-1}
s_00 s_01 ... s_0(n-1)
...                    (matriz n x n de similitudes, simétrica, s_ii = 1)
```

**Salida**: una línea por camión, con los índices (desde 0) de sus productos separados por espacio.

## 8. Estructura del proyecto

```
src/
  instancia.*        lectura de la instancia
  solucion.*         solución, función objetivo, factibilidad y escritura
  temperatura.*      los tres modos de temperatura
  constructivas.*    BFD, MOCHILA y COSTO (y FFD como base)
  busqueda_local.*   relocate, swap y vaciar camión
  metaheuristica.*   GRASP con búsqueda local
  main.cpp           modo interactivo y modo línea de comandos
experimentacion/     scripts de gráficos y experimentos
generador/           generador de instancias
instancias/          instancias de entrada
resultados/          salidas: una carpeta solucion_<fecha_hora> por corrida, y las de los experimentos
presentacion/        presentación para la defensa oral (index.html, o presentacion_completa.html en un solo archivo)
```

## 9. Qué falta

- [x] Modelo: alpha, beta y temperatura.
- [x] Constructivas BFD, MOCHILA y COSTO.
- [x] Búsqueda local: relocate, swap y vaciar camión.
- [x] Metaheurística: GRASP con búsqueda local.
- [x] Experimentación con suite controlada y barrido alpha/beta.
- [ ] Completar los datos finales de integrantes, grupo y fecha en el informe.

> **Uso de IA:** las heurísticas constructivas (BFD, MOCHILA, COSTO y FFD) y la infraestructura de este proyecto (lectura y escritura, menú, gráficos y scripts de experimentos) se hicieron con asistencia de IA. Hay que compartir la conversación en la entrega.

## 10. Fechas

- Entrega (informe + código): **24 de noviembre de 2026, 23:59**.
- Presentaciones: **26 y 27 de noviembre de 2026**.
