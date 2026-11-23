#!/usr/bin/env python3
"""Mide la sensibilidad de alpha y beta sobre un lote de instancias."""
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


EXE_DEFECTO = "tp2.exe" if os.name == "nt" else "./tp2"


def leer_instancia(path):
    with open(path, "r", encoding="utf-8") as f:
        tok = f.read().split()
    it = iter(tok)
    n = int(next(it))
    C = float(next(it))
    pesos = []
    temps = []
    for _ in range(n):
        pesos.append(float(next(it)))
        temps.append(float(next(it)))
    sim = [[float(next(it)) for _ in range(n)] for _ in range(n)]
    s_max = sum(sim[i][j] for i in range(n) for j in range(i + 1, n))
    return n, C, pesos, temps, sim, s_max


def leer_solucion(path):
    camiones = []
    with open(path, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                camiones.append([int(x) for x in linea.split()])
    return camiones


def similitud_total(camiones, sim):
    total = 0.0
    for bin_ in camiones:
        for pos_a, a in enumerate(bin_):
            for b in bin_[pos_a + 1:]:
                total += sim[a][b]
    return total


def cota_inferior(pesos, C, temps, delta, modo):
    if modo != "delta" or math.isinf(delta):
        return math.ceil(sum(pesos) / C - 1e-9)

    orden = sorted(range(len(pesos)), key=lambda i: temps[i])
    total = 0
    peso_grupo = 0.0
    for pos, i in enumerate(orden):
        if pos > 0 and temps[i] - temps[orden[pos - 1]] > delta + 1e-9:
            total += math.ceil(peso_grupo / C - 1e-9)
            peso_grupo = 0.0
        peso_grupo += pesos[i]
    return total + math.ceil(peso_grupo / C - 1e-9)


def correr(exe, inst, out, metodo, alpha, beta, delta, modo, iteraciones, semilla):
    if os.path.exists(exe):
        exe = os.path.abspath(exe)
    t0 = time.perf_counter()
    res = subprocess.run(
        [exe, inst, out, metodo, str(alpha), str(beta), str(delta), modo,
         str(iteraciones), str(semilla)],
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - t0
    if res.returncode != 0:
        print(f"ERROR {metodo} en {inst}: {res.stderr}", file=sys.stderr)
        sys.exit(1)
    return leer_solucion(out), elapsed


def main():
    ap = argparse.ArgumentParser(
        description="Barrer factores de alpha y beta respecto de 1/S_max"
    )
    ap.add_argument("--instdir", default="instancias/lote_dificil")
    ap.add_argument("--exe", default=EXE_DEFECTO)
    ap.add_argument("--metodos", default="bfd,costo")
    ap.add_argument("--alphas", default="0.5,1,2")
    ap.add_argument("--beta-factors", default="0.25,0.5,1,2,4")
    ap.add_argument("--beta-values", default=None,
                     help='valores beta absolutos separados por coma; "auto" usa 1/S_max')
    ap.add_argument("--delta", type=float, default=6.0)
    ap.add_argument("--modo", default="delta", choices=["delta", "bandas", "hibrido"])
    ap.add_argument("--iteraciones", type=int, default=200)
    ap.add_argument("--semilla", type=int, default=42)
    ap.add_argument("--csv", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    metodos = [m.strip() for m in args.metodos.split(",") if m.strip()]
    alphas = [float(x.strip()) for x in args.alphas.split(",") if x.strip()]
    beta_factors = [float(x.strip()) for x in args.beta_factors.split(",") if x.strip()]
    beta_values = None
    if args.beta_values:
        beta_values = [x.strip() for x in args.beta_values.split(",") if x.strip()]
    instancias = sorted(glob.glob(os.path.join(args.instdir, "*.txt")))
    if not instancias:
        print(f"No hay instancias en {args.instdir}", file=sys.stderr)
        sys.exit(1)

    carpeta = preparar_carpeta(
        "experimentacion_alpha_beta",
        args,
        csv="alpha_beta.csv",
        out="alpha_beta.png",
    )
    filas = []
    tmp = os.path.join(carpeta, "_tmp.out")

    for inst in instancias:
        n, C, pesos, temps, sim, s_max = leer_instancia(inst)
        lower = cota_inferior(pesos, C, temps, args.delta, args.modo)
        beta_auto = 1.0 / s_max if s_max > 0 else 0.0

        for alpha in alphas:
            experiment_betas = (
                [(float(v) if v != "auto" else beta_auto,
                  (float(v) / beta_auto if v != "auto" and beta_auto > 0 else 1.0),
                  v)
                 for v in beta_values]
                if beta_values
                else [(factor * beta_auto, factor, f"{factor:g}x") for factor in beta_factors]
            )
            for beta, factor, beta_label in experiment_betas:
                for metodo in metodos:
                    camiones, elapsed = correr(
                        args.exe, inst, tmp, metodo, alpha, beta,
                        args.delta, args.modo, args.iteraciones, args.semilla,
                    )
                    K = len(camiones)
                    S = similitud_total(camiones, sim)
                    gap = (K - lower) / lower if lower > 0 else 0.0
                    filas.append({
                        "instancia": os.path.basename(inst),
                        "n": n,
                        "metodo": metodo,
                        "alpha": alpha,
                        "beta_factor": factor,
                        "beta_label": beta_label,
                        "beta": beta,
                        "S_max": s_max,
                        "K": K,
                        "lower": lower,
                        "gap": gap,
                        "S": S,
                        "objetivo": alpha * K - beta * S,
                        "tiempo": elapsed,
                    })

    if os.path.exists(tmp):
        os.remove(tmp)

    campos = list(filas[0].keys())
    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(filas)

    resumen = {}
    print("\nResumen promedio (mas bajo es mejor para K/gap; mas alto es mejor para S):")
    print(f"{'metodo':8} {'alpha':>7} {'beta_factor':>12} {'K':>8} {'gap':>9} {'S':>10}")
    resumen_factors = sorted({r["beta_factor"] for r in filas})
    for metodo in metodos:
        for alpha in alphas:
            for factor in resumen_factors:
                sub = [r for r in filas
                       if r["metodo"] == metodo
                       and r["alpha"] == alpha
                       and r["beta_factor"] == factor]
                key = (metodo, alpha, factor)
                resumen[key] = {
                    "K": sum(r["K"] for r in sub) / len(sub),
                    "gap": sum(r["gap"] for r in sub) / len(sub),
                    "S": sum(r["S"] for r in sub) / len(sub),
                    "objetivo": sum(r["objetivo"] for r in sub) / len(sub),
                }
                value = resumen[key]
                print(f"{metodo:8} {alpha:7g} {factor:12g} "
                      f"{value['K']:8.2f} {100 * value['gap']:8.2f}% "
                      f"{value['S']:10.1f}")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for metodo in metodos:
        for alpha in alphas:
            ks = []
            ss = []
            for factor in resumen_factors:
                value = resumen[(metodo, alpha, factor)]
                ks.append(value["K"])
                ss.append(value["S"])
            axes[0].plot(resumen_factors, ks, marker="o",
                         label=f"{metodo}, alpha={alpha:g}")
            axes[1].plot(resumen_factors, ss, marker="o",
                         label=f"{metodo}, alpha={alpha:g}")

    axes[0].axvline(1.0, color="gray", linestyle="--", label="beta = 1/S_max")
    axes[1].axvline(1.0, color="gray", linestyle="--", label="beta = 1/S_max")
    axes[0].set_xlabel("factor sobre beta = 1/S_max")
    axes[0].set_ylabel("K promedio")
    axes[0].set_title("Camiones")
    axes[1].set_xlabel("factor sobre beta = 1/S_max")
    axes[1].set_ylabel("similitud promedio")
    axes[1].set_title("Similitud")
    for ax in axes:
        ax.set_xscale("log")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)

    fig.suptitle(
        f"Sensibilidad alpha/beta ({len(instancias)} instancias, "
        f"delta={args.delta:g}, modo={args.modo})"
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(args.out, dpi=130)
    print(f"\nCSV guardado en: {args.csv}")
    print(f"Grafico guardado en: {args.out}")


if __name__ == "__main__":
    main()
