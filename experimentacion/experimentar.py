#!/usr/bin/env python3
"""Ejecuta comparaciones reproducibles de los algoritmos desde la terminal."""

import argparse
import csv
import glob
import math
import os
import statistics
import subprocess
import sys
import time


def leer_instancia(path):
    with open(path, "r", encoding="utf-8") as f:
        tokens = f.read().split()

    if not tokens:
        raise RuntimeError(f"Instancia vacia: {path}")

    it = iter(tokens)
    n = int(next(it))
    capacidad = float(next(it))
    pesos = []
    temperaturas = []
    for _ in range(n):
        pesos.append(float(next(it)))
        temperaturas.append(float(next(it)))

    similitudes = [[float(next(it)) for _ in range(n)] for _ in range(n)]
    return n, capacidad, pesos, temperaturas, similitudes


def leer_solucion(path):
    camiones = []
    with open(path, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                camiones.append([int(x) for x in linea.split()])
    return camiones


def cota_inferior(pesos, temperaturas, capacidad, delta, modo):
    peso_total = sum(pesos)
    if modo != "delta" or math.isinf(delta):
        return math.ceil(peso_total / capacidad - 1e-9)

    orden = sorted(range(len(pesos)), key=lambda i: temperaturas[i])
    total = 0
    peso_grupo = 0.0
    for pos, i in enumerate(orden):
        if pos > 0 and temperaturas[i] - temperaturas[orden[pos - 1]] > delta + 1e-9:
            total += math.ceil(peso_grupo / capacidad - 1e-9)
            peso_grupo = 0.0
        peso_grupo += pesos[i]
    total += math.ceil(peso_grupo / capacidad - 1e-9)
    return total


def temperatura_a_banda(temperatura):
    setpoints = (-18.0, 4.0, 20.0, 65.0)
    return min(range(len(setpoints)),
               key=lambda i: abs(temperatura - setpoints[i]))


def calcular_metricas(camiones, pesos, temperaturas, similitudes, capacidad,
                      delta, modo, alpha, beta):
    if not camiones:
        return None

    vistos = [0] * len(pesos)
    pesos_camion = []
    rangos_temperatura = []
    similitud_total = 0.0
    peso_excedido = False
    temperatura_excedida = False

    for camion in camiones:
        peso_camion = sum(pesos[i] for i in camion)
        pesos_camion.append(peso_camion)
        peso_excedido |= peso_camion > capacidad + 1e-9

        temps = [temperaturas[i] for i in camion]
        rango = max(temps) - min(temps)
        rangos_temperatura.append(rango)
        if modo == "delta" and rango > delta + 1e-9:
            temperatura_excedida = True
        elif modo == "bandas":
            bandas = [temperatura_a_banda(t) for t in temps]
            if len(set(bandas)) != 1:
                temperatura_excedida = True
        elif modo == "hibrido":
            setpoints = (-18.0, 4.0, 20.0, 65.0)
            temperatura_excedida |= not any(
                all(abs(t - setpoint) <= delta + 1e-9 for t in temps)
                for setpoint in setpoints
            )

        for i in camion:
            vistos[i] += 1
        for pos, i in enumerate(camion):
            for j in camion[pos + 1:]:
                similitud_total += similitudes[i][j]

    factible = (
        not peso_excedido
        and not temperatura_excedida
        and all(v == 1 for v in vistos)
    )
    utilizacion = sum(pesos_camion) / (len(camiones) * capacidad)
    mejor_utilizacion = max(p / capacidad for p in pesos_camion)
    peor_utilizacion = min(p / capacidad for p in pesos_camion)
    k = len(camiones)

    return {
        "K": k,
        "factible": factible,
        "objetivo": alpha * k - beta * similitud_total,
        "S": similitud_total,
        "utilizacion_promedio": utilizacion,
        "utilizacion_mejor": mejor_utilizacion,
        "utilizacion_peor": peor_utilizacion,
        "rango_temp_max": max(rangos_temperatura),
    }


def similitud_maxima(similitudes):
    n = len(similitudes)
    return sum(similitudes[i][j] for i in range(n) for j in range(i + 1, n))


def ejecutar(exe, instancia, salida, metodo, alpha, beta, delta, modo,
            iteraciones=None, semilla=None):
    comando = [
        exe, instancia, salida, metodo,
        str(alpha), str(beta), str(delta), modo,
    ]
    if iteraciones is not None:
        comando += [str(iteraciones), str(semilla)]

    inicio = time.perf_counter()
    proceso = subprocess.run(comando, capture_output=True, text=True)
    tiempo = time.perf_counter() - inicio
    if proceso.returncode != 0:
        raise RuntimeError(
            f"Error ejecutando {metodo} en {instancia}\n"
            f"{proceso.stderr}"
        )
    return leer_solucion(salida), tiempo


def promedio_grupo(filas, clave):
    valores = [fila[clave] for fila in filas]
    return statistics.mean(valores)


def lista(texto, tipo):
    return [tipo(x.strip()) for x in texto.split(",") if x.strip()]


def main():
    ap = argparse.ArgumentParser(description="Comparar algoritmos de Bin Packing")
    ap.add_argument("--instdir", default="instancias/lote")
    ap.add_argument("--exe", default="tp2.exe" if os.name == "nt" else "./tp2")
    ap.add_argument("--metodos", default="bfd,mochila,costo",
                    help="separados por coma: bfd,mochila,costo,ffd,meta")
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--beta", default="auto")
    ap.add_argument("--delta", type=float, default=6.0)
    ap.add_argument("--modo", default="delta",
                    choices=["delta", "bandas", "hibrido"])
    ap.add_argument("--iteraciones", default="100,500,1000",
                    help="valores GRASP separados por coma")
    ap.add_argument("--semillas", default="1,2,3",
                    help="semillas separadas por coma")
    ap.add_argument("--repeticiones", type=int, default=1,
                    help="repeticiones de las constructivas")
    ap.add_argument("--csv", default="resultados/experimentacion.csv")
    args = ap.parse_args()

    metodos = [m.strip().lower() for m in args.metodos.split(",") if m.strip()]
    iteraciones = lista(args.iteraciones, int)
    semillas = lista(args.semillas, int)
    instancias = sorted(glob.glob(os.path.join(args.instdir, "*.txt")))
    if not instancias:
        raise SystemExit(f"No hay instancias .txt en {args.instdir}")

    if not os.path.exists(args.exe):
        raise SystemExit(
            f"No existe el ejecutable '{args.exe}'. "
            "Compilalo primero con g++ -std=c++17 -O2 -Isrc -o tp2.exe src/*.cpp"
        )

    os.makedirs(os.path.dirname(args.csv) or ".", exist_ok=True)
    salida_tmp = os.path.join(os.path.dirname(args.csv) or ".", "_experimentacion_tmp.out")
    filas = []

    for instancia in instancias:
        n, capacidad, pesos, temperaturas, similitudes = leer_instancia(instancia)
        s_max = similitud_maxima(similitudes)
        beta = 1.0 / s_max if args.beta == "auto" else float(args.beta)
        cota = cota_inferior(pesos, temperaturas, capacidad, args.delta, args.modo)

        configuraciones = []
        for metodo in metodos:
            if metodo == "meta":
                for iteracion in iteraciones:
                    for semilla in semillas:
                        configuraciones.append((metodo, iteracion, semilla))
            else:
                for repeticion in range(args.repeticiones):
                    configuraciones.append((metodo, "", repeticion + 1))

        for metodo, iteracion, semilla in configuraciones:
            if metodo == "meta":
                camiones, tiempo = ejecutar(
                    os.path.abspath(args.exe), instancia, salida_tmp,
                    metodo, args.alpha, args.beta, args.delta, args.modo,
                    iteracion, semilla,
                )
            else:
                camiones, tiempo = ejecutar(
                    os.path.abspath(args.exe), instancia, salida_tmp,
                    metodo, args.alpha, args.beta, args.delta, args.modo,
                )

            metricas = calcular_metricas(
                camiones, pesos, temperaturas, similitudes, capacidad,
                args.delta, args.modo, args.alpha, beta,
            )
            gap = (metricas["K"] - cota) / cota if cota else 0.0
            filas.append({
                "instancia": os.path.basename(instancia),
                "n": n,
                "metodo": metodo,
                "config": iteracion if metodo == "meta" else semilla,
                "semilla": semilla if metodo == "meta" else "",
                "K": metricas["K"],
                "cota_K": cota,
                "gap_pct": 100 * gap,
                "S": round(metricas["S"], 6),
                "S_norm": round(metricas["S"] / s_max, 6) if s_max else 0.0,
                "objetivo": round(metricas["objetivo"], 6),
                "utilizacion_promedio": round(metricas["utilizacion_promedio"], 6),
                "utilizacion_mejor": round(metricas["utilizacion_mejor"], 6),
                "utilizacion_peor": round(metricas["utilizacion_peor"], 6),
                "rango_temp_max": round(metricas["rango_temp_max"], 6),
                "factible": metricas["factible"],
                "tiempo_ms": round(1000 * tiempo, 3),
            })

            estado = "OK" if metricas["factible"] else "NO FACTIBLE"
            config_txt = f" it={iteracion} seed={semilla}" if metodo == "meta" else ""
            print(
                f"{os.path.basename(instancia):24} "
                f"{metodo:8}{config_txt:20} "
                f"K={metricas['K']:5d} gap={100 * gap:7.2f}% "
                f"S_norm={metricas['S'] / s_max if s_max else 0.0:7.4f} "
                f"obj={metricas['objetivo']:10.4f} "
                f"t={1000 * tiempo:9.1f} ms {estado}"
            )

    if os.path.exists(salida_tmp):
        os.remove(salida_tmp)

    campos = [
        "instancia", "n", "metodo", "config", "semilla", "K", "cota_K",
        "gap_pct", "S", "S_norm", "objetivo", "utilizacion_promedio",
        "utilizacion_mejor", "utilizacion_peor", "rango_temp_max",
        "factible", "tiempo_ms",
    ]
    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(filas)

    print("\nResumen por metodo/configuracion:")
    print(
        f"{'metodo/config':20} {'K':>7} {'gap%':>8} "
        f"{'S_norm':>8} {'objetivo':>11} {'util%':>8} {'t(ms)':>10}"
    )
    grupos = {}
    for fila in filas:
        clave = (
            f"{fila['metodo']} it={fila['config']}"
            if fila["metodo"] == "meta"
            else fila["metodo"]
        )
        grupos.setdefault(clave, []).append(fila)

    for clave, grupo in grupos.items():
        print(
            f"{clave:20} "
            f"{promedio_grupo(grupo, 'K'):7.2f} "
            f"{promedio_grupo(grupo, 'gap_pct'):8.2f} "
            f"{promedio_grupo(grupo, 'S_norm'):8.4f} "
            f"{promedio_grupo(grupo, 'objetivo'):11.4f} "
            f"{100 * promedio_grupo(grupo, 'utilizacion_promedio'):7.2f}% "
            f"{promedio_grupo(grupo, 'tiempo_ms'):10.1f}"
        )

    print(f"\nCSV guardado en: {args.csv}")
    print(f"Corridas realizadas: {len(filas)}")


if __name__ == "__main__":
    main()
