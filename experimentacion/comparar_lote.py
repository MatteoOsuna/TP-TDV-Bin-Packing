#!/usr/bin/env python3
"""Corre las heuristicas sobre una carpeta de instancias y compara K, gap, similitud y tiempo.

Uso: python experimentacion/comparar_lote.py --instdir instancias/lote
"""
import argparse
import csv
import glob
import math
import os
import subprocess
import sys
import time
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from carpetas import preparar_carpeta

METODOS = ["bfd", "mochila", "costo"]  # agregar "meta" cuando este lista
EXE_DEFECTO = "tp2.exe" if os.name == "nt" else "./tp2"


def leer_instancia(path):
    with open(path, "r", encoding="utf-8") as f:
        tok = f.read().split()
    it = iter(tok)
    n = int(next(it))
    C = float(next(it))
    pesos, temps = [], []
    for _ in range(n):
        pesos.append(float(next(it)))
        temps.append(float(next(it)))
    sim = [[float(next(it)) for _ in range(n)] for _ in range(n)]
    return n, C, pesos, temps, sim


def leer_solucion(path):
    camiones = []
    with open(path, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                camiones.append([int(x) for x in linea.split()])
    return camiones


def cota_inferior(pesos, temps, C, delta, modo):
    """Cota inferior de camiones.

    Solo con el peso: ceil(sum(w) / C). En modo delta se afina con la temperatura:
    se ordenan los productos por temperatura y se corta donde el salto entre dos
    consecutivos supera delta; productos de lados distintos del corte nunca pueden
    compartir camion (su diferencia seria > delta), asi que cada grupo necesita
    por lo menos ceil(peso del grupo / C) camiones.
    """
    if modo != "delta" or math.isinf(delta):
        return math.ceil(sum(pesos) / C - 1e-9)
    orden = sorted(range(len(pesos)), key=lambda i: temps[i])
    total, peso_grupo = 0, 0.0
    for pos, i in enumerate(orden):
        if pos > 0 and temps[i] - temps[orden[pos - 1]] > delta + 1e-9:
            total += math.ceil(peso_grupo / C - 1e-9)
            peso_grupo = 0.0
        peso_grupo += pesos[i]
    return total + math.ceil(peso_grupo / C - 1e-9)


def similitud_total(camiones, sim):
    total = 0.0
    for bin_ in camiones:
        for a in range(len(bin_)):
            for b in range(a + 1, len(bin_)):
                total += sim[bin_[a]][bin_[b]]
    return total


def correr(exe, inst, metodo, out, alpha, beta, delta, modo):
    if os.path.exists(exe):
        exe = os.path.abspath(exe)
    t0 = time.perf_counter()
    res = subprocess.run(
        [exe, inst, out, metodo, str(alpha), str(beta), str(delta), modo],
        capture_output=True, text=True,
    )
    dt = time.perf_counter() - t0
    if res.returncode != 0:
        print(f"ERROR {metodo} en {inst}:\n{res.stderr}", file=sys.stderr)
        sys.exit(1)
    return leer_solucion(out), dt


def main():
    ap = argparse.ArgumentParser(description="Comparar heuristicas en lote")
    ap.add_argument("--instdir", default="instancias/lote", help="carpeta con instancias")
    ap.add_argument("--exe", default=EXE_DEFECTO)
    ap.add_argument("--metodos", default=",".join(METODOS),
                    help="heuristicas a comparar, separadas por coma (default: bfd,mochila,costo)")
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--beta", default="auto", help='numero o "auto" = 1/S_max')
    ap.add_argument("--delta", type=float, default=float("inf"))
    ap.add_argument("--modo", default="delta", choices=["delta", "bandas", "hibrido"])
    ap.add_argument("--csv", default=None, help="(default: en una carpeta nueva con fecha dentro de resultados/)")
    ap.add_argument("--out", default=None, help="(default: en una carpeta nueva con fecha dentro de resultados/)")
    args = ap.parse_args()
    metodos = [m.strip() for m in args.metodos.split(",") if m.strip()]

    instancias = sorted(glob.glob(os.path.join(args.instdir, "*.txt")))
    if not instancias:
        print(f"No hay instancias en {args.instdir}", file=sys.stderr)
        sys.exit(1)

    carpeta = preparar_carpeta("comparacion_lote", args,
                               csv="comparacion_lote.csv", out="comparacion_lote.png")
    tmp = f"{carpeta}/_tmp.out"
    filas = []

    for inst in instancias:
        n, C, pesos, temps, sim = leer_instancia(inst)
        L = cota_inferior(pesos, temps, C, args.delta, args.modo)
        S_max = sum(sim[i][j] for i in range(n) for j in range(i + 1, n))
        beta = (1.0 / S_max if S_max > 0 else 0.0) if args.beta == "auto" else float(args.beta)
        for metodo in metodos:
            camiones, dt = correr(args.exe, inst, metodo, tmp, args.alpha, args.beta, args.delta, args.modo)
            K = len(camiones)
            S = similitud_total(camiones, sim)
            gap = (K - L) / L if L > 0 else 0.0
            filas.append({
                "instancia": os.path.basename(inst), "n": n, "metodo": metodo,
                "K": K, "L": L, "gap": gap, "S": round(S, 3),
                "objetivo": round(args.alpha * K - beta * S, 5), "tiempo": round(dt, 4),
            })
    if os.path.exists(tmp):
        os.remove(tmp)

    # --- CSV ---
    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["instancia", "n", "metodo", "K", "L", "gap", "S", "objetivo", "tiempo"])
        w.writeheader()
        w.writerows(filas)
    print(f"CSV guardado en: {args.csv}  ({len(filas)} filas)")

    # --- Resumen por metodo ---
    print("\nResumen (promedio sobre todas las instancias):")
    print(f"{'metodo':8} {'gap medio':>10} {'K medio':>9} {'S media':>9} {'objetivo':>9} {'t medio (ms)':>13}")
    for m in metodos:
        sub = [r for r in filas if r["metodo"] == m]
        gm = 100 * sum(r["gap"] for r in sub) / len(sub)
        km = sum(r["K"] for r in sub) / len(sub)
        sm = sum(r["S"] for r in sub) / len(sub)
        om = sum(r["objetivo"] for r in sub) / len(sub)
        tm = 1000 * sum(r["tiempo"] for r in sub) / len(sub)
        print(f"{m:8} {gm:>9.2f}% {km:>9.2f} {sm:>9.1f} {om:>9.3f} {tm:>13.1f}")

    # --- Graficos ---
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16, 5))

    # (1) Boxplot del gap por metodo.
    datos_gap = [[100 * r["gap"] for r in filas if r["metodo"] == m] for m in metodos]
    ax1.boxplot(datos_gap, showmeans=True)
    ax1.set_xticklabels(metodos)  # compatible con cualquier version de matplotlib
    ax1.set_ylabel("gap de camiones (%)  =  (K - L) / L")
    ax1.set_title("Calidad: gap vs cota inferior\n(mas bajo = mejor; cota con temperatura en modo delta)")
    ax1.grid(axis="y", alpha=0.3)

    # (2) K vs n (promedio por metodo).
    for m in metodos:
        por_n = defaultdict(list)
        for r in filas:
            if r["metodo"] == m:
                por_n[r["n"]].append(r["K"])
        ns = sorted(por_n)
        ks = [sum(por_n[nn]) / len(por_n[nn]) for nn in ns]
        ax2.plot(ns, ks, marker="o", label=m)
    ax2.set_xlabel("n (cantidad de productos)")
    ax2.set_ylabel("K medio (camiones)")
    ax2.set_title("Escalabilidad: camiones vs tamanio")
    ax2.legend()
    ax2.grid(alpha=0.3)

    # (3) gap vs n (promedio por metodo).
    for m in metodos:
        por_n = defaultdict(list)
        for r in filas:
            if r["metodo"] == m:
                por_n[r["n"]].append(100 * r["gap"])
        ns = sorted(por_n)
        gs = [sum(por_n[nn]) / len(por_n[nn]) for nn in ns]
        ax3.plot(ns, gs, marker="s", label=m)
    ax3.set_xlabel("n (cantidad de productos)")
    ax3.set_ylabel("gap medio (%)")
    ax3.set_title("Calidad vs tamanio")
    ax3.legend()
    ax3.grid(alpha=0.3)

    fig.suptitle(
        f"Comparacion en lote  ({len(instancias)} instancias, "
        f"delta={'sin limite' if args.delta == float('inf') else f'{args.delta:g}'}, modo={args.modo})",
        fontsize=13,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(args.out, dpi=130)
    print(f"\nGrafico guardado en: {args.out}")


if __name__ == "__main__":
    main()
