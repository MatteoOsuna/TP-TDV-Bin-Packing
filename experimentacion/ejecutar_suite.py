#!/usr/bin/env python3
"""Genera un lote manejable y ejecuta la bateria principal de experimentos."""

import argparse
import csv
import glob
import math
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime

from experimentar import (
    calcular_metricas,
    cota_inferior,
    leer_instancia,
    leer_solucion,
    similitud_maxima,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERADOR = os.path.join(ROOT, "generador", "generador.py")
SRC_FILES = sorted(glob.glob(os.path.join(ROOT, "src", "*.cpp")))


def compilar_si_hace_falta(exe):
    fuentes = [
        os.path.join(ROOT, "src", name)
        for name in os.listdir(os.path.join(ROOT, "src"))
        if name.endswith(".cpp")
    ]
    binario_viejo = not os.path.exists(exe) or any(
        os.path.getmtime(path) > os.path.getmtime(exe) for path in fuentes
    )
    if not binario_viejo:
        return
    if not SRC_FILES:
        raise RuntimeError("No se encontraron fuentes C++ en src/")

    comando = [
        "g++", "-std=c++17", "-O2", "-static", "-Isrc",
        "-o", os.path.relpath(exe, ROOT),
    ] + [os.path.relpath(path, ROOT) for path in SRC_FILES]
    print("Compilando ejecutable:", " ".join(comando), flush=True)
    subprocess.run(comando, cwd=ROOT, check=True)


def generar_instancias(sizes, seeds, capacities, force=False, perfil="categorias",
                       carpeta="suite"):
    directorio_base = os.path.join(ROOT, "instancias", carpeta)
    os.makedirs(directorio_base, exist_ok=True)
    instancias = []

    for capacidad in capacities:
        directorio = os.path.join(directorio_base, f"C{capacidad:g}")
        os.makedirs(directorio, exist_ok=True)
        for n in sizes:
            for seed in seeds:
                prefijo = "" if perfil == "categorias" else f"{perfil}_"
                path = os.path.join(directorio, f"inst_{prefijo}n{n}_s{seed}.txt")
                if force or not os.path.exists(path):
                    comando = [
                        sys.executable, GENERADOR,
                        "--n", str(n),
                        "--C", str(capacidad),
                        "--seed", str(seed),
                        "--perfil-temperatura", perfil,
                        "--out", path,
                    ]
                    subprocess.run(comando, cwd=ROOT, check=True)
                instancias.append((path, n, capacidad, seed))
    return instancias


def ejecutar(exe, path_inst, path_out, metodo, alpha, beta, delta, modo,
             iteraciones=None, semilla=None):
    comando = [
        exe, path_inst, path_out, metodo,
        str(alpha), str(beta), str(delta), modo,
    ]
    if iteraciones is not None:
        comando += [str(iteraciones), str(semilla)]

    inicio = time.perf_counter()
    proceso = subprocess.run(comando, cwd=ROOT, capture_output=True, text=True)
    elapsed = time.perf_counter() - inicio
    if proceso.returncode != 0:
        raise RuntimeError(
            f"Fallo {metodo} en {os.path.basename(path_inst)}:\n{proceso.stderr}"
        )
    return leer_solucion(path_out), elapsed


def cota_suite(pesos, temps, capacidad, delta, modo):
    if modo == "delta":
        return cota_inferior(pesos, temps, capacidad, delta, modo)

    setpoints = (-18.0, 4.0, 20.0, 65.0)
    if modo == "bandas":
        grupos = [[] for _ in setpoints]
        for peso, temperatura in zip(pesos, temps):
            banda = min(range(len(setpoints)),
                        key=lambda i: abs(temperatura - setpoints[i]))
            grupos[banda].append(peso)
        return sum(
            math.ceil(sum(grupo) / capacidad - 1e-9)
            for grupo in grupos if grupo
        )

    # Para delta < 8 los intervalos de los setpoints no se solapan.
    # Cada producto pertenece entonces a un unico grupo termico.
    if delta < 8:
        grupos = [[] for _ in setpoints]
        for peso, temperatura in zip(pesos, temps):
            banda = min(range(len(setpoints)),
                        key=lambda i: abs(temperatura - setpoints[i]))
            grupos[banda].append(peso)
        return sum(
            math.ceil(sum(grupo) / capacidad - 1e-9)
            for grupo in grupos if grupo
        )

    return cota_inferior(pesos, temps, capacidad, delta, modo)


def resolver_exacto_pequeno(pesos, temps, similitudes, capacidad, beta, delta):
    n = len(pesos)
    if n > 12:
        raise ValueError("El benchmark exacto esta limitado a n <= 12.")

    inicio = time.perf_counter()
    cantidad = 1 << n
    peso_sub = [0.0] * cantidad
    sim_sub = [0.0] * cantidad
    tmin_sub = [float("inf")] * cantidad
    tmax_sub = [float("-inf")] * cantidad
    factible = [False] * cantidad
    factible[0] = True

    for mask in range(1, cantidad):
        bit = mask & -mask
        i = bit.bit_length() - 1
        resto = mask ^ bit
        peso_sub[mask] = peso_sub[resto] + pesos[i]
        tmin_sub[mask] = min(tmin_sub[resto], temps[i])
        tmax_sub[mask] = max(tmax_sub[resto], temps[i])
        sim_sub[mask] = sim_sub[resto] + sum(
            similitudes[i][j] for j in range(n) if resto & (1 << j)
        )
        factible[mask] = (
            peso_sub[mask] <= capacidad + 1e-9
            and tmax_sub[mask] - tmin_sub[mask] <= delta + 1e-9
        )

    mejor_obj = [float("inf")] * cantidad
    mejor_k = [0] * cantidad
    elegido = [0] * cantidad
    mejor_obj[0] = 0.0

    for mask in range(1, cantidad):
        ancla = mask & -mask
        sub = mask
        while sub:
            resto = mask ^ sub
            if sub & ancla and factible[sub] and mejor_obj[resto] < float("inf"):
                candidato = mejor_obj[resto] + 1.0 - beta * sim_sub[sub]
                if candidato < mejor_obj[mask] - 1e-12:
                    mejor_obj[mask] = candidato
                    mejor_k[mask] = mejor_k[resto] + 1
                    elegido[mask] = sub
            sub = (sub - 1) & mask

    elapsed = time.perf_counter() - inicio
    if mejor_obj[-1] == float("inf"):
        raise RuntimeError("La instancia pequena no tiene solucion factible exacta.")

    bins = []
    mask = cantidad - 1
    while mask:
        sub = elegido[mask]
        if sub == 0:
            raise RuntimeError("No se pudo reconstruir la solucion exacta.")
        bins.append([i for i in range(n) if sub & (1 << i)])
        mask ^= sub
    return bins, mejor_k[-1], mejor_obj[-1], elapsed


def registrar(
    filas, phase, metodo, config, path_inst, n, capacidad, semilla_instancia,
    alpha, beta, delta, modo, iteraciones, semilla_meta,
    pesos, temps, similitudes, camiones, elapsed, perfil="categorias",
    optimo=None,
):
    s_max = similitud_maxima(similitudes)
    metricas = calcular_metricas(
        camiones, pesos, temps, similitudes, capacidad, delta, modo, alpha, beta
    )
    if metricas is None:
        raise RuntimeError(f"El metodo {metodo} devolvio una solucion vacia.")

    cota = cota_suite(pesos, temps, capacidad, delta, modo)
    gap = (metricas["K"] - cota) / cota if cota else 0.0
    fila = {
        "fase": phase,
        "config": config,
        "instancia": os.path.basename(path_inst),
        "n": n,
        "capacidad": capacidad,
        "semilla_instancia": semilla_instancia,
        "perfil_temperatura": perfil,
        "metodo": metodo,
        "modo_temperatura": modo,
        "delta": delta,
        "alpha": alpha,
        "beta": beta,
        "iteraciones_meta": iteraciones if iteraciones is not None else "",
        "semilla_meta": semilla_meta if metodo == "meta" else "",
        "K": metricas["K"],
        "cota_K": cota,
        "gap_pct": round(100 * gap, 4),
        "S": round(metricas["S"], 6),
        "S_norm": round(metricas["S"] / s_max, 6) if s_max else 0.0,
        "objetivo": round(metricas["objetivo"], 6),
        "utilizacion_promedio": round(metricas["utilizacion_promedio"], 6),
        "rango_temp_max": round(metricas["rango_temp_max"], 6),
        "factible": metricas["factible"],
        "tiempo_ms": round(1000 * elapsed, 3),
        "K_optimo": optimo["K"] if optimo else "",
        "delta_objetivo_optimo": (
            round(metricas["objetivo"] - optimo["objetivo"], 8) if optimo else ""
        ),
    }
    filas.append(fila)
    estado = "OK" if metricas["factible"] else "NO FACTIBLE"
    print(
        f"[{phase:15}] n={n:4} C={capacidad:5g} "
        f"{metodo:7} {modo:7} K={metricas['K']:4} "
        f"S_norm={fila['S_norm']:.4f} t={fila['tiempo_ms']:9.1f} ms {estado}",
        flush=True,
    )


def resumen(filas):
    grupos = {}
    for fila in filas:
        clave = (
            fila["fase"], fila["perfil_temperatura"], fila["metodo"],
            fila["modo_temperatura"], fila["delta"], fila["iteraciones_meta"],
        )
        grupos.setdefault(clave, []).append(fila)

    print("\nRESUMEN POR FASE (media +/- desvio; tiempo mediano)")
    print(
        f"{'fase':18} {'perfil':12} {'metodo':8} {'modo':8} {'delta':>5} "
        f"{'iter':>5} {'K media +/- sd':>17} {'gap%':>7} "
        f"{'S_norm +/- sd':>17} {'fact%':>7} {'t med ms':>10}"
    )
    for clave, grupo in sorted(grupos.items(), key=lambda item: str(item[0])):
        phase, perfil, metodo, modo, delta, iteraciones = clave
        factibles = sum(bool(f["factible"]) for f in grupo)
        k_values = [f["K"] for f in grupo]
        sn_values = [f["S_norm"] for f in grupo]
        k_sd = statistics.stdev(k_values) if len(k_values) > 1 else 0.0
        sn_sd = statistics.stdev(sn_values) if len(sn_values) > 1 else 0.0
        print(
            f"{phase:18} {perfil:12} {metodo:8} {modo:8} {delta:5g} "
            f"{str(iteraciones):>5} "
            f"{statistics.mean(k_values):7.2f} +/- {k_sd:5.2f} "
            f"{statistics.mean(f['gap_pct'] for f in grupo):7.2f} "
            f"{statistics.mean(sn_values):7.4f} +/- {sn_sd:7.4f} "
            f"{100 * factibles / len(grupo):6.1f}% "
            f"{statistics.median(f['tiempo_ms'] for f in grupo):10.1f}"
        )

    escala = {}
    for fila in filas:
        if fila["fase"] != "comparacion":
            continue
        clave = (fila["n"], fila["capacidad"], fila["metodo"])
        escala.setdefault(clave, []).append(fila)

    print("\nESCALABILIDAD (por tamaño/capacidad; mediana de tiempo)")
    print(f"{'n':>6} {'C':>6} {'metodo':8} {'K medio':>8} {'gap%':>7} {'t med ms':>10}")
    for clave, grupo in sorted(escala.items()):
        n, capacidad, metodo = clave
        print(
            f"{n:6} {capacidad:6g} {metodo:8} "
            f"{statistics.mean(f['K'] for f in grupo):8.2f} "
            f"{statistics.mean(f['gap_pct'] for f in grupo):7.2f} "
            f"{statistics.median(f['tiempo_ms'] for f in grupo):10.1f}"
        )

def main():
    parser = argparse.ArgumentParser(
        description="Bateria reproducible de heuristicas, temperatura y META."
    )
    parser.add_argument("--exe", default="tp2.exe" if os.name == "nt" else "tp2")
    parser.add_argument("--sizes", default="100,250,500,1000",
                        help="productos por instancia")
    parser.add_argument("--seeds", default="1,2,3,4,5",
                        help="semillas para las instancias")
    parser.add_argument("--capacities", default="20,100",
                        help="capacidades separadas por coma")
    parser.add_argument("--delta", type=float, default=6.0)
    parser.add_argument("--deltas", default="2,4,6,8,12",
                        help="deltas del barrido termico")
    parser.add_argument("--temp-sizes", default=None,
                        help="tamanos para las instancias de frontera")
    parser.add_argument("--sin-barrido-temperatura", action="store_true",
                        help="omitir el barrido de delta y perfiles termicos")
    parser.add_argument("--meta-tuning", dest="meta_tuning", action="store_true",
                        help="incluir una comparacion META acotada (100 iteraciones)")
    parser.add_argument("--sin-meta-tuning", dest="meta_tuning",
                        action="store_false",
                        help="omitir la comparacion META")
    parser.add_argument("--regenerar", action="store_true",
                        help="volver a generar las instancias aunque ya existan")
    parser.add_argument("--outdir", default=None,
                        help="carpeta de resultados (por defecto, una carpeta con fecha)")
    parser.set_defaults(meta_tuning=True)
    args = parser.parse_args()

    exe = args.exe if os.path.isabs(args.exe) else os.path.join(ROOT, args.exe)
    compilar_si_hace_falta(exe)

    sizes = [int(x) for x in args.sizes.split(",") if x.strip()]
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    capacities = [float(x) for x in args.capacities.split(",") if x.strip()]
    deltas = [float(x) for x in args.deltas.split(",") if x.strip()]
    instancias = generar_instancias(sizes, seeds, capacities, args.regenerar)

    marca = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    outdir = os.path.abspath(
        args.outdir or os.path.join(ROOT, "resultados", f"suite_{marca}")
    )
    os.makedirs(outdir, exist_ok=True)
    salida = os.path.join(outdir, "resultados.csv")
    temp_out = os.path.join(outdir, "_solucion_tmp.out")
    filas = []

    # Comparacion central: varias semillas, heuristicas y modelos termicos.
    for path, n, capacidad, seed in instancias:
        _, _, pesos, temps, similitudes = leer_instancia(path)
        s_max = similitud_maxima(similitudes)
        beta_auto = 1.0 / s_max if s_max else 0.0
        for modo in ("delta", "bandas", "hibrido"):
            for metodo in ("ffd", "bfd", "mochila", "costo"):
                camiones, elapsed = ejecutar(
                    exe, path, temp_out, metodo, 1.0, "auto", args.delta, modo
                )
                registrar(
                    filas, "comparacion", metodo, "base", path, n, capacidad, seed,
                    1.0, beta_auto, args.delta, modo, None, None,
                    pesos, temps, similitudes, camiones, elapsed,
                )

    # Las instancias categorias permiten aislar el efecto de delta=2.
    # El perfil fronteras crea casos cercanos a los cambios entre modelos.
    if not args.sin_barrido_temperatura:
        seed_representativa = seeds[0]
        delta_dos = any(abs(delta - 2.0) < 1e-9 for delta in deltas)
        if delta_dos:
            muestra_cat = [
                item for item in instancias
                if item[1] == min(sizes) and item[3] == seed_representativa
            ]
            for path, n, capacidad, seed in muestra_cat:
                _, _, pesos, temps, similitudes = leer_instancia(path)
                s_max = similitud_maxima(similitudes)
                beta_auto = 1.0 / s_max if s_max else 0.0
                for modo in ("delta", "bandas", "hibrido"):
                    for metodo in ("ffd", "bfd", "mochila", "costo"):
                        camiones, elapsed = ejecutar(
                            exe, path, temp_out, metodo, 1.0, "auto", 2.0, modo
                        )
                        registrar(
                            filas, "barrido_delta", metodo, "temperatura",
                            path, n, capacidad, seed, 1.0, beta_auto, 2.0,
                            modo, None, None, pesos, temps, similitudes,
                            camiones, elapsed, perfil="categorias",
                        )

        deltas_frontera = [delta for delta in deltas if delta >= 4.0]
        if deltas_frontera:
            if args.temp_sizes:
                temp_sizes = [
                    int(x) for x in args.temp_sizes.split(",") if x.strip()
                ]
            else:
                temp_sizes = [n for n in (100, 500) if n in sizes]
                if not temp_sizes:
                    temp_sizes = [min(sizes)]
            instancias_frontera = generar_instancias(
                temp_sizes, [seed_representativa], capacities,
                force=args.regenerar, perfil="fronteras",
                carpeta="suite_fronteras",
            )
            for delta in deltas_frontera:
                for path, n, capacidad, seed in instancias_frontera:
                    _, _, pesos, temps, similitudes = leer_instancia(path)
                    s_max = similitud_maxima(similitudes)
                    beta_auto = 1.0 / s_max if s_max else 0.0
                    for modo in ("delta", "bandas", "hibrido"):
                        for metodo in ("ffd", "bfd", "mochila", "costo"):
                            camiones, elapsed = ejecutar(
                                exe, path, temp_out, metodo, 1.0, "auto",
                                delta, modo,
                            )
                            registrar(
                                filas, "barrido_delta", metodo, "temperatura",
                                path, n, capacidad, seed, 1.0, beta_auto, delta,
                                modo, None, None, pesos, temps, similitudes,
                                camiones, elapsed, perfil="fronteras",
                            )

    # Benchmark exacto de n pequeno: sirve para medir el gap real, no solo
    # el gap respecto de una cota inferior.
    exactas = generar_instancias(
        [10], seeds[:3], [min(capacities)], force=args.regenerar,
        carpeta="suite_exacta",
    )
    for path, n, capacidad, seed in exactas:
        _, _, pesos, temps, similitudes = leer_instancia(path)
        s_max = similitud_maxima(similitudes)
        beta_auto = 1.0 / s_max if s_max else 0.0
        bins_optimos, k_optimo, obj_optimo, elapsed = resolver_exacto_pequeno(
            pesos, temps, similitudes, capacidad, beta_auto, args.delta
        )
        referencia = {"K": k_optimo, "objetivo": obj_optimo}
        registrar(
            filas, "optimo_exacto", "exacto", "DP_subconjuntos", path, n,
            capacidad, seed, 1.0, beta_auto, args.delta, "delta", None, None,
            pesos, temps, similitudes, bins_optimos, elapsed,
            perfil="categorias", optimo=referencia,
        )
        for metodo in ("ffd", "bfd", "mochila", "costo"):
            camiones, elapsed = ejecutar(
                exe, path, temp_out, metodo, 1.0, "auto", args.delta, "delta"
            )
            registrar(
                filas, "optimo_exacto", metodo, "comparacion_exacta", path,
                n, capacidad, seed, 1.0, beta_auto, args.delta, "delta",
                None, None, pesos, temps, similitudes, camiones, elapsed,
                perfil="categorias", optimo=referencia,
            )

    # Una sola configuracion de META (100 iteraciones), tres semillas
    # aleatorias y cuatro casos representativos; no se barre la configuracion.
    if args.meta_tuning:
        meta_sizes = [n for n in (100, 250) if n in sizes]
        if not meta_sizes:
            meta_sizes = [min(sizes)]
        seleccion = [
            item for item in instancias
            if item[3] == seeds[0]
            and item[2] in (min(capacities), max(capacities))
            and item[1] in meta_sizes
        ]
        for path, n, capacidad, seed in seleccion:
            _, _, pesos, temps, similitudes = leer_instancia(path)
            s_max = similitud_maxima(similitudes)
            beta_auto = 1.0 / s_max if s_max else 0.0
            for semilla_meta in (1, 2, 3):
                iteraciones = 100
                camiones, elapsed = ejecutar(
                    exe, path, temp_out, "meta", 1.0, "auto",
                    args.delta, "delta", iteraciones, semilla_meta,
                )
                registrar(
                    filas, "meta_comparacion", "meta", "GRASP_100",
                    path, n, capacidad, seed, 1.0, beta_auto,
                    args.delta, "delta", iteraciones, semilla_meta, pesos, temps,
                    similitudes, camiones, elapsed,
                )

    if os.path.exists(temp_out):
        os.remove(temp_out)
    if not filas:
        raise RuntimeError("La bateria no genero resultados.")

    campos = list(filas[0].keys())
    with open(salida, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=campos)
        writer.writeheader()
        writer.writerows(filas)

    resumen(filas)
    print(f"\nInstancias usadas: {len(instancias)}")
    print(f"Corridas: {len(filas)}")
    print(f"Resultados CSV: {salida}")


if __name__ == "__main__":
    main()
