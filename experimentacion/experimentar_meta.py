#!/usr/bin/env python3
"""Experimentos de la metaheuristica: varias semillas, tuning de iteraciones y comparacion
contra las constructivas.

Para cada instancia corre:
  - las constructivas (bfd, mochila, costo) una sola vez: son deterministas;
  - la metaheuristica ("meta") con cada valor de --iteraciones y cada semilla de --semillas.

Guarda un CSV con todas las corridas, un resumen por configuracion y un grafico.

Uso (desde la carpeta del proyecto):
  python experimentacion/experimentar_meta.py --instdir instancias/lote_dificil --delta 6
  python experimentacion/experimentar_meta.py --instdir instancias/lote --iteraciones 100,500,2000 --semillas 1,2,3,4,5
"""
import argparse
import csv
import glob
import math
import os
import statistics
import subprocess
import sys
import time
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from carpetas import preparar_carpeta
from comparar_lote import cota_inferior, leer_instancia, leer_solucion, similitud_total

EXE_DEFECTO = "tp2.exe" if os.name == "nt" else "./tp2"
BASE = ["bfd", "mochila", "costo"]


def correr(exe, inst, out, metodo, alpha, beta, delta, modo, iteraciones=None, semilla=None):
    """Corre tp2 y devuelve (camiones, segundos). La CLI es:
    tp2 <in> <out> <metodo> <alpha> <beta> <delta> <modo> [iteraciones] [semilla]"""
    if os.path.exists(exe):
        exe = os.path.abspath(exe)
    cmd = [exe, inst, out, metodo, str(alpha), str(beta), str(delta), modo]
    if iteraciones is not None:
        cmd += [str(iteraciones), str(semilla)]
    t0 = time.perf_counter()
    res = subprocess.run(cmd, capture_output=True, text=True)
    dt = time.perf_counter() - t0
    if res.returncode != 0:
        print(f"ERROR {metodo} en {inst}:\n{res.stderr}", file=sys.stderr)
        sys.exit(1)
    return leer_solucion(out), dt


def lista(texto, tipo):
    return [tipo(x) for x in texto.split(",") if x.strip()]


def main():
    ap = argparse.ArgumentParser(description="Experimentos de la metaheuristica")
    ap.add_argument("--instdir", default="instancias/lote_dificil", help="carpeta con instancias")
    ap.add_argument("--exe", default=EXE_DEFECTO)
    ap.add_argument("--iteraciones", default="100,500,1000",
                    help="valores de iteraciones a probar (tuning), separados por coma")
    ap.add_argument("--semillas", default="1,2,3,4,5", help="semillas, separadas por coma")
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--beta", default="auto", help='numero o "auto" = 1/S_max')
    ap.add_argument("--delta", type=float, default=6.0)
    ap.add_argument("--modo", default="delta", choices=["delta", "bandas", "hibrido"])
    ap.add_argument("--csv", default=None, help="(default: carpeta nueva con fecha en resultados/)")
    ap.add_argument("--out", default=None, help="(default: carpeta nueva con fecha en resultados/)")
    args = ap.parse_args()

    iteraciones = lista(args.iteraciones, int)
    semillas = lista(args.semillas, int)
    instancias = sorted(glob.glob(os.path.join(args.instdir, "*.txt")))
    if not instancias:
        print(f"No hay instancias en {args.instdir}", file=sys.stderr)
        sys.exit(1)

    carpeta = preparar_carpeta("experimento_meta", args,
                               csv="experimento_meta.csv", out="experimento_meta.png")
    tmp = f"{carpeta}/_tmp.out"
    filas = []

    def registrar(inst, n, C, pesos, temps, sim, S_max, beta, camiones, dt, metodo, config, semilla):
        K = len(camiones)
        S = similitud_total(camiones, sim)
        L = cota_inferior(pesos, temps, C, args.delta, args.modo)
        filas.append({
            "instancia": os.path.basename(inst), "n": n, "metodo": metodo,
            "iteraciones": config, "semilla": semilla,
            "K": K, "L": L, "gap": round((K - L) / L, 5) if L else 0.0,
            "S": round(S, 4), "S_norm": round(S / S_max, 5) if S_max else 0.0,
            "obj_camiones_primero": round(args.alpha * K - beta * S, 6),   # K - S/S_max
            "obj_similitud_primero": round(args.alpha * K - 1.0 * S, 4),   # K - S (beta = 1)
            "tiempo": round(dt, 4),
        })

    for inst in instancias:
        n, C, pesos, temps, sim = leer_instancia(inst)
        S_max = sum(sim[i][j] for i in range(n) for j in range(i + 1, n))
        beta = (1.0 / S_max if S_max > 0 else 0.0) if args.beta == "auto" else float(args.beta)
        print(f"{os.path.basename(inst)} ...", flush=True)

        for m in BASE:  # deterministas: una sola corrida
            cam, dt = correr(args.exe, inst, tmp, m, args.alpha, args.beta, args.delta, args.modo)
            registrar(inst, n, C, pesos, temps, sim, S_max, beta, cam, dt, m, "", "")
        for it in iteraciones:
            for sem in semillas:
                cam, dt = correr(args.exe, inst, tmp, "meta", args.alpha, args.beta,
                                 args.delta, args.modo, it, sem)
                registrar(inst, n, C, pesos, temps, sim, S_max, beta, cam, dt, "meta", it, sem)
    if os.path.exists(tmp):
        os.remove(tmp)

    # --- CSV con todas las corridas ---
    campos = ["instancia", "n", "metodo", "iteraciones", "semilla", "K", "L", "gap", "S", "S_norm",
              "obj_camiones_primero", "obj_similitud_primero", "tiempo"]
    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)
    print(f"\nCSV guardado en: {args.csv}  ({len(filas)} corridas)")

    # --- Resumen por configuracion ---
    # Para meta: primero se promedia sobre las semillas de cada instancia y despues sobre
    # las instancias. "desv" = desvio entre semillas (promedio sobre instancias).
    configs = [(m, "") for m in BASE] + [("meta", it) for it in iteraciones]
    resumen = {}
    print("\nResumen (promedio sobre instancias; meta: promedio sobre semillas):")
    print(f"{'config':16} {'K medio':>8} {'gap %':>7} {'S_norm':>8} {'desv S_norm':>12} "
          f"{'obj':>9} {'t (ms)':>8}")
    for metodo, it in configs:
        sub = [r for r in filas if r["metodo"] == metodo and r["iteraciones"] == it]
        por_inst = defaultdict(list)
        for r in sub:
            por_inst[r["instancia"]].append(r)
        k = statistics.mean(statistics.mean(x["K"] for x in v) for v in por_inst.values())
        gap = statistics.mean(statistics.mean(x["gap"] for x in v) for v in por_inst.values())
        sn = statistics.mean(statistics.mean(x["S_norm"] for x in v) for v in por_inst.values())
        desv = statistics.mean(
            (statistics.pstdev(x["S_norm"] for x in v) if len(v) > 1 else 0.0)
            for v in por_inst.values())
        obj = statistics.mean(
            statistics.mean(x["obj_camiones_primero"] for x in v) for v in por_inst.values())
        t = statistics.mean(statistics.mean(x["tiempo"] for x in v) for v in por_inst.values())
        nombre = metodo if it == "" else f"meta it={it}"
        resumen[(metodo, it)] = dict(k=k, gap=gap, sn=sn, desv=desv, obj=obj, t=t)
        print(f"{nombre:16} {k:>8.2f} {100 * gap:>7.2f} {sn:>8.4f} {desv:>12.5f} "
              f"{obj:>9.4f} {1000 * t:>8.1f}")

    # --- Grafico ---
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16, 5))
    colores = {"bfd": "#378ADD", "mochila": "#E24B4A", "costo": "#1D9E75"}

    # (1) similitud normalizada vs iteraciones, con las constructivas como referencia.
    ys = [resumen[("meta", it)]["sn"] for it in iteraciones]
    es = [resumen[("meta", it)]["desv"] for it in iteraciones]
    ax1.errorbar(iteraciones, ys, yerr=es, marker="o", color="black", capsize=4,
                 label="meta (media ± desvio entre semillas)")
    for m in BASE:
        ax1.axhline(resumen[(m, "")]["sn"], linestyle="--", color=colores[m], label=m)
    ax1.set_xscale("log")
    ax1.set_xlabel("iteraciones")
    ax1.set_ylabel("S / S_max (similitud juntada)")
    ax1.set_title("Tuning: similitud vs iteraciones\n(mas alto = mejor)")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)

    # (2) camiones medios.
    ks = [resumen[("meta", it)]["k"] for it in iteraciones]
    ax2.plot(iteraciones, ks, marker="o", color="black", label="meta")
    for m in BASE:
        ax2.axhline(resumen[(m, "")]["k"], linestyle="--", color=colores[m], label=m)
    ax2.set_xscale("log")
    ax2.set_xlabel("iteraciones")
    ax2.set_ylabel("K medio (camiones)")
    ax2.set_title("Camiones vs iteraciones\n(mas bajo = mejor)")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)

    # (3) tiempo.
    ts = [1000 * resumen[("meta", it)]["t"] for it in iteraciones]
    ax3.plot(iteraciones, ts, marker="s", color="black")
    ax3.set_xscale("log")
    ax3.set_yscale("log")
    ax3.set_xlabel("iteraciones")
    ax3.set_ylabel("tiempo por corrida (ms)")
    ax3.set_title("Costo en tiempo")
    ax3.grid(alpha=0.3)

    delta_txt = "sin limite" if math.isinf(args.delta) else f"{args.delta:g}"
    fig.suptitle(f"Metaheuristica: {len(instancias)} instancias x {len(semillas)} semillas "
                 f"(delta={delta_txt}, modo={args.modo})", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(args.out, dpi=130)
    print(f"Grafico guardado en: {args.out}")


if __name__ == "__main__":
    main()
