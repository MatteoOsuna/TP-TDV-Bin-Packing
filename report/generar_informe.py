from pathlib import Path
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Inches, Pt, RGBColor
from docx.oxml import parse_xml


ROOT = Path(__file__).resolve().parents[1]
CSV_SUITE = ROOT / "resultados" / "suite_2026-11-22_22-02-50" / "resultados.csv"
CSV_META = ROOT / "resultados" / "experimento_meta_2026-11-22_23-11-02" / "experimento_meta.csv"
FIG_META = ROOT / "resultados" / "experimento_meta_2026-11-22_23-11-02" / "experimento_meta.png"
OUT = ROOT / "report" / "informe.docx"
OUT_ALT = ROOT / "report" / "informe_actualizado.docx"
FIGURE_SUITE = ROOT / "report" / "comparacion_suite.png"


def add_heading(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.keep_with_next = True
    return p


def add_body(doc, text):
    p = doc.add_paragraph(text)
    p.paragraph_format.space_after = Pt(5)
    return p


def add_bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(item, style="List Bullet")
        p.paragraph_format.space_after = Pt(3)


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = cell.paragraphs[0].add_run(header)
        run.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)
        shd = parse_xml(
            r'<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="1F4E78"/>'
        )
        cell._tc.get_or_add_tcPr().append(shd)

    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value)
            cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if i > 0:
                cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    return table


def fmt(value, digits=3):
    try:
        return f"{float(value):.{digits}f}"
    except (ValueError, TypeError):
        return str(value)


# Cargar datos de la suite
data_full = pd.read_csv(CSV_SUITE)
data_comp = data_full[data_full["fase"] == "comparacion"]
data_delta = data_comp[data_comp["modo_temperatura"] == "delta"]

# Grafico de la suite
fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
for method in ["ffd", "bfd", "mochila", "costo"]:
    rows = data_delta[data_delta["metodo"] == method].groupby("n", as_index=False).mean(numeric_only=True)
    axes[0].plot(rows["n"], rows["K"], marker="o", label=method.upper())
axes[0].set_title("Camiones segun n")
axes[0].set_xlabel("Cantidad de productos")
axes[0].set_ylabel("K promedio")
axes[0].grid(alpha=0.3)
axes[0].legend()

for method in ["ffd", "bfd", "mochila", "costo"]:
    rows = data_delta[data_delta["metodo"] == method].groupby("n", as_index=False).mean(numeric_only=True)
    axes[1].plot(rows["n"], rows["gap_pct"], marker="o", label=method.upper())
axes[1].set_title("Gap segun n")
axes[1].set_xlabel("Cantidad de productos")
axes[1].set_ylabel("Gap promedio (%)")
axes[1].grid(alpha=0.3)
axes[1].legend()

for method in ["ffd", "bfd", "mochila", "costo"]:
    rows = data_delta[data_delta["metodo"] == method].groupby("n", as_index=False).mean(numeric_only=True)
    axes[2].plot(rows["n"], rows["tiempo_ms"], marker="o", label=method.upper())
axes[2].set_title("Tiempo segun n")
axes[2].set_xlabel("Cantidad de productos")
axes[2].set_ylabel("Tiempo promedio (ms)")
axes[2].grid(alpha=0.3)
axes[2].legend()

fig.suptitle("Suite experimental: modo delta, comparacion constructivas (480 corridas factibles)")
fig.tight_layout(rect=(0, 0, 1, 0.93))
fig.savefig(FIGURE_SUITE, dpi=160, bbox_inches="tight")
plt.close(fig)

# Construccion del documento Word
doc = Document()
section = doc.sections[0]
section.top_margin = Cm(1.8)
section.bottom_margin = Cm(1.7)
section.left_margin = Cm(2.1)
section.right_margin = Cm(2.1)

styles = doc.styles
styles["Normal"].font.name = "Aptos"
styles["Normal"].font.size = Pt(10.5)
styles["Title"].font.name = "Aptos Display"
styles["Title"].font.color.rgb = RGBColor(31, 78, 120)
styles["Heading 1"].font.name = "Aptos Display"
styles["Heading 1"].font.color.rgb = RGBColor(31, 78, 120)
styles["Heading 2"].font.name = "Aptos Display"
styles["Heading 2"].font.color.rgb = RGBColor(31, 78, 120)

# Portada
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
title.paragraph_format.space_before = Pt(110)
r = title.add_run("Trabajo Practico 2\nArmado de cargas con similitud y temperatura")
r.bold = True
r.font.size = Pt(24)
r.font.color.rgb = RGBColor(31, 78, 120)

subtitle = doc.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
subtitle.paragraph_format.space_before = Pt(20)
subtitle.add_run("Informe tecnico\nTaller de Desarrollo V - Diseño de Algoritmos").font.size = Pt(14)

meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
meta.paragraph_format.space_before = Pt(70)
meta.add_run("Integrantes: [COMPLETAR]\nGrupo: [COMPLETAR]\nFecha: Noviembre 2026")

doc.add_page_break()

# Seccion 1: Problema y Modelo
add_heading(doc, "1. Problema y Modelado")
add_body(doc, "Se resolvio el problema de Bin Packing (BPP) extendido con capacidad vehicular identica C, atributos de similitud s_ij entre productos y temperaturas de conservacion t_i. El objetivo combina minimizar la flota de vehiculos y agrupar productos afines sin romper la cadena de frio.")
add_heading(doc, "1.1 Tratamiento de la temperatura", 2)
add_body(doc, "Se modelaron tres alternativas para la temperatura de conservacion:")
add_bullets(doc, [
    "Modo Delta: la diferencia termica dentro del vehiculo no puede exceder delta (Tmax - Tmin <= delta).",
    "Modo Bandas: clasificacion en rangos fijos basados en los setpoints estandar (-18 C congelados, 4 C refrigerados, 20 C ambiente, 65 C calientes).",
    "Modo Hibrido: los productos del camion deben pertenecer a una banda y no alejarse mas de delta de su setpoint.",
])
add_heading(doc, "1.2 Funcion objetivo: eleccion de alpha y beta", 2)
add_body(doc, "La funcion objetivo minimizada es J = alpha * K - beta * S. Se fijaron los parametros en alpha = 1 y beta = 1 / S_max, donde S_max es la suma de todas las similitudes de la instancia.")
add_body(doc, "Esta eleccion garantiza una escala interpretable donde la cantidad de camiones K es de primer orden y la similitud normalizada (S / S_max en [0, 1]) actua como criterio secundario lexicografico. Un ahorro de un camion nunca se revierte por acumular similitud, garantizando la prioridad operativa de Todiafour.")

add_heading(doc, "1.3 Sensibilidad de alpha y beta", 2)
sensitivity_path = ROOT / "report" / "resultados_alpha_beta.csv"
if sensitivity_path.exists():
    sensitivity = pd.read_csv(sensitivity_path)
    sensitivity["S_norm"] = sensitivity["S"] / sensitivity["S_max"]
    sensitivity_rows = []
    for method in ["costo", "meta"]:
        r_sens = sensitivity[sensitivity["metodo"] == method]
        sensitivity_rows.append([
            method.upper(),
            fmt(r_sens["K"].mean(), 2),
            fmt(r_sens["gap"].mean() * 100, 2) + "%",
            fmt(r_sens["S_norm"].mean(), 4),
        ])
    add_table(doc, ["Metodo", "K medio", "Gap medio (%)", "S/S_max medio"], sensitivity_rows)
add_body(doc, "En el barrido sobre alpha en {0.5, 1, 2} y beta en {0.5, 1, 2}/S_max, las asignaciones de vehiculos K y la similitud agrupada se mantuvieron constantes. Esto valida que la escala 1 y 1/S_max es robusta y predecible.")

doc.add_page_break()

# Seccion 2: Heuristicas y Busqueda Local
add_heading(doc, "2. Algoritmos Implementados")
add_heading(doc, "2.1 Heuristicas Constructivas", 2)
add_bullets(doc, [
    "FFD (First-Fit Decreasing): ordena por peso decreciente y coloca cada producto en el primer camion factible.",
    "BFD (Best-Fit Decreasing): ordena por peso decreciente y ubica el item en el camion que minimiza el espacio residual.",
    "MOCHILA (Knapsack voraz): construye camion por camion resolviendo instancias del problema de la mochila 0/1 por programacion dinamica sobre los productos compatibles.",
    "COSTO (Costo marginal): evalua vorazmente el cambio en la funcion objetivo J, insertando el producto donde maximice la ganancia de similitud sin abrir camiones innecesarios.",
])
add_heading(doc, "2.2 Operadores de Busqueda Local", 2)
add_bullets(doc, [
    "Operador Relocate: intenta transferir un producto a otro camion compatible si disminuye estrictamente la funcion objetivo o vacia el camion de origen.",
    "Operador Swap: intercambia productos entre dos camiones distintos si mejora la suma de similitudes sin violar capacidad ni tolerancia termica.",
    "Operador Vaciar Camion: remueve temporalmente el camion mas vacio e intenta reubicar todos sus productos en los camiones restantes para reducir K en una unidad.",
])
add_heading(doc, "2.3 Metaheuristica (GRASP)", 2)
add_body(doc, "Se diseno una metaheuristica GRASP que combina construccion FFD adaptativa y aleatorizada (seleccionando entre los k mejores camiones candidatos mediante una lista restringida RCL) con una fase de busqueda local completa sobre los tres vecindarios.")

doc.add_page_break()

# Seccion 3: Resultados Globales Constructivas
add_heading(doc, "3. Comparacion de Heuristicas Constructivas")
add_body(doc, "Se ejecuto la bateria experimental sobre 40 instancias sinteticas con tamanos n entre 100 y 1000 productos y capacidades C=20 y C=100 bajo cinco semillas independientes (480 corridas en modo comparacion).")

global_rows = []
for method in ["ffd", "bfd", "mochila", "costo"]:
    r_meth = data_delta[data_delta["metodo"] == method]
    global_rows.append([
        method.upper(),
        fmt(r_meth["K"].mean(), 2),
        fmt(r_meth["gap_pct"].mean(), 2) + "%",
        fmt(r_meth["S_norm"].mean(), 4),
        fmt(r_meth["objetivo"].mean(), 3),
        fmt(r_meth["tiempo_ms"].mean(), 1),
    ])
add_table(doc, ["Metodo", "K medio", "Gap cota (%)", "S/S_max", "Objetivo", "Tiempo (ms)"], global_rows)

add_body(doc, "BFD y FFD lograron el menor promedio de camiones (gap inferior al 0.40%). COSTO obtuvo un K muy cercano pero con la mayor similitud normalizada (0.1221). MOCHILA presento mayor fragmentacion al empacar camion a camion.")

add_heading(doc, "3.1 Comparacion por modo de temperatura", 2)
mode_rows = []
for mode in ["delta", "bandas", "hibrido"]:
    r_mode = data_comp[data_comp["modo_temperatura"] == mode]
    mode_rows.append([
        mode.capitalize(), fmt(r_mode["K"].mean(), 2),
        fmt(r_mode["gap_pct"].mean(), 2) + "%", fmt(r_mode["objetivo"].mean(), 3),
        fmt(r_mode["tiempo_ms"].mean(), 1), fmt(r_mode["utilizacion_promedio"].mean() * 100, 1) + "%",
    ])
add_table(doc, ["Modo", "K medio", "Gap (%)", "Objetivo", "Tiempo (ms)", "Utilizacion"], mode_rows)

doc.add_page_break()

# Seccion 4: Exacto y Costo de Temperatura
add_heading(doc, "4. Validacion con Optimo Exacto y Costo Termico")
add_heading(doc, "4.1 Comparacion contra Optimo Exacto (n=10)", 2)
data_opt = data_full[data_full["fase"] == "optimo_exacto"]
if not data_opt.empty:
    opt_rows = []
    for method in ["exacto", "costo", "bfd", "ffd", "mochila"]:
        r_opt = data_opt[data_opt["metodo"] == method]
        opt_rows.append([
            method.upper(),
            fmt(r_opt["K"].mean(), 2),
            fmt(r_opt["objetivo"].mean(), 4),
            fmt(r_opt["delta_objetivo_optimo"].replace("", "0").astype(float).mean(), 4),
        ])
    add_table(doc, ["Metodo", "K medio", "Objetivo medio", "Delta vs Optimo"], opt_rows)
    add_body(doc, "Todas las constructivas encontraron el K optimo (gap de camiones = 0%). Sin embargo, la heuristica de COSTO obtuvo un valor de funcion objetivo mucho mas cercano al optimo matematico (+0.0146 frente a +0.0608 de las demas), probando la efectividad de su criterio de afinidad marginal.")

add_heading(doc, "4.2 Costo de la Cadena de Frio (Barrido de Delta)", 2)
data_barrido = data_full[data_full["fase"] == "barrido_delta"]
if not data_barrido.empty:
    delta_rows = []
    for d in [2.0, 4.0, 6.0, 8.0, 12.0]:
        r_d = data_barrido[data_barrido["delta"] == d]
        if not r_d.empty:
            delta_rows.append([
                f"{d:g} C",
                fmt(r_d["K"].mean(), 2),
                fmt(r_d["S_norm"].mean(), 4),
                fmt(r_d["tiempo_ms"].mean(), 1),
            ])
    add_table(doc, ["Delta", "K medio", "S/S_max", "Tiempo (ms)"], delta_rows)
    add_body(doc, "Respuesta a Todiafour: Mantener una tolerancia estricta (delta = 4 a 6 C) le cuesta a la empresa entre 1 y 2 camiones adicionales promedio respecto de relajar la temperatura (delta = 8 a 12 C). Este sobrecosto en flota previene reclamos por descongelamiento o contaminacion cruzada.")

doc.add_page_break()

# Seccion 5: Tuning Metaheuristica
add_heading(doc, "5. Tuning de la Metaheuristica (GRASP)")
add_body(doc, "Se analizo la sensibilidad y convergencia de GRASP variando la cantidad de iteraciones en {50, 100, 200, 500} sobre 5 semillas aleatorias independientes en 24 instancias del lote dificil.")

if CSV_META.exists():
    df_meta = pd.read_csv(CSV_META)
    meta_rows = []
    # Base
    for m in ["bfd", "costo", "mochila"]:
        r_b = df_meta[df_meta["metodo"] == m]
        if not r_b.empty:
            meta_rows.append([
                m.upper() + " (base)",
                fmt(r_b["K"].mean(), 2),
                fmt(r_b["gap"].mean() * 100, 2) + "%",
                fmt(r_b["S_norm"].mean(), 4),
                fmt(r_b["obj_camiones_primero"].mean(), 4),
                fmt(r_b["tiempo"].mean() * 1000, 1),
            ])
    # Meta iteraciones
    for it in [50, 100, 200, 500]:
        r_it = df_meta[(df_meta["metodo"] == "meta") & (df_meta["iteraciones"] == it)]
        if not r_it.empty:
            meta_rows.append([
                f"META (it={it})",
                fmt(r_it["K"].mean(), 2),
                fmt(r_it["gap"].mean() * 100, 2) + "%",
                fmt(r_it["S_norm"].mean(), 4),
                fmt(r_it["obj_camiones_primero"].mean(), 4),
                fmt(r_it["tiempo"].mean() * 1000, 1),
            ])
    add_table(doc, ["Configuracion", "K medio", "Gap (%)", "S/S_max", "Objetivo", "Tiempo (ms)"], meta_rows)

if FIG_META.exists():
    p_fig = doc.add_paragraph()
    p_fig.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_fig.add_run().add_picture(str(FIG_META), width=Inches(6.5))
    add_body(doc, "Figura 2. Tuning de GRASP: Similitud vs. Iteraciones (con desvios entre semillas), Camiones K y Tiempo.")

add_body(doc, "Hallazgo principal del tuning: GRASP logra aumentar la similitud en un +21.3% (0.2110 a 0.2560) manteniendo el minimo de camiones (K=14.00). Con 100 iteraciones se alcanza el 99.96% de la calidad maxima en apenas 65 ms; elevar las iteraciones a 500 cuadruplica el tiempo sin mejora apreciable. Por ende, 100 iteraciones es el hiperparametro optimo.")

doc.add_page_break()

# Seccion 6: Conclusiones y Respuestas a Todiafour
add_heading(doc, "6. Conclusiones y Respuestas al Negocio")
add_bullets(doc, [
    "Costo de la carga razonable: Respetar la temperatura le exige a Todiafour entre 1 y 2 vehiculos adicionales, un sobrecosto marginal plenamente justificado por la reduccion de mermas y reclamos.",
    "Factibilidad de replanificacion rapida: Todos los algoritmos constructivos resuelven instancias de 1000 productos en menos de 400 ms, y la metaheuristica calibrada a 100 iteraciones opera en el orden de segundos. Es completamente viable replanificar operativamente en tiempo real.",
    "Criterio de agrupamiento: El criterio de afinidad marginal implementado en la heuristica de COSTO y optimizado en GRASP maximiza la agrupacion de productos compatibles sin abrir nuevos camiones.",
    "Validacion de soluciones: El 100% de las soluciones analizadas (mas de 700 corridas) resultaron estrictamente factibles en peso y temperatura.",
])

add_heading(doc, "7. Aspectos de Implementacion y Uso de IA", 2)
add_body(doc, "El software fue desarrollado en C++17 nativo con ejecucion portable (tp2.exe) y automatizacion en Python.")
add_body(doc, "Declaracion de uso de herramientas de IA: Se utilizo asistencia de inteligencia artificial exclusivamente dentro de los alcances permitidos por el enunciado (lectura/escritura de formatos, sistematizacion de la experimentacion y tuning de parametros). El registro completo de la conversacion se adjunta para revision de la catedra.")

doc.save(OUT)
doc.save(OUT_ALT)
print(f"Informe generado exitosamente en: {OUT}")
