#!/usr/bin/env python3
"""Genera instancias con el formato del enunciado.

Similitudes y temperaturas salen de categorias de producto: misma categoria ->
similitud alta y temperatura parecida.

Uso: python generador/generador.py --n 50 --C 100 --seed 1 --out instancias/inst_50.txt
"""
import argparse
import os
import random


# Categorias de ejemplo: (nombre, temperatura_tipica_C, rango_peso)
CATEGORIAS = [
    ("congelado", -18, (2, 8)),    # helados, congelados
    ("refrigerado", 4, (1, 6)),    # lacteos, carnes
    ("ambiente", 20, (1, 10)),     # secos, enlatados
    ("caliente", 65, (1, 4)),      # comida lista
    ("limpieza", 20, (3, 12)),     # detergentes, quimicos
]

TEMPERATURAS_FRONTERA = {
    0: (-22, -18, -14),
    1: (0, 4, 8),
    2: (16, 20, 24),
    3: (61, 65, 69),
    4: (16, 20, 24),
}


def temperatura_producto(cat_idx: int, rng: random.Random, perfil: str):
    if perfil == "fronteras":
        return rng.choice(TEMPERATURAS_FRONTERA[cat_idx])
    _, t_base, _ = CATEGORIAS[cat_idx]
    return round(t_base + rng.uniform(-2, 2), 1)


def generar(n: int, capacidad: float, seed: int, perfil_temperatura: str = "categorias"):
    rng = random.Random(seed)

    # Asignar una categoria a cada producto.
    cat_idx = [rng.randrange(len(CATEGORIAS)) for _ in range(n)]

    pesos, temps = [], []
    for i in range(n):
        _, _, (wmin, wmax) = CATEGORIAS[cat_idx[i]]
        pesos.append(round(rng.uniform(wmin, wmax), 2))
        temps.append(temperatura_producto(cat_idx[i], rng, perfil_temperatura))

    # Similitud: alta dentro de la misma categoria, baja entre categorias.
    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        sim[i][i] = 1.0
        for j in range(i + 1, n):
            if cat_idx[i] == cat_idx[j]:
                s = rng.uniform(0.7, 1.0)
            else:
                s = rng.uniform(0.0, 0.3)
            sim[i][j] = sim[j][i] = round(s, 2)

    return pesos, temps, sim


def escribir(path: str, capacidad: float, pesos, temps, sim):
    n = len(pesos)
    carpeta = os.path.dirname(path)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{n} {capacidad}\n")
        for i in range(n):
            f.write(f"{pesos[i]} {temps[i]}\n")
        for i in range(n):
            f.write(" ".join(str(sim[i][j]) for j in range(n)) + "\n")


def escribir_grande(path: str, capacidad: float, n: int, seed: int,
                    perfil_temperatura: str = "categorias"):
    rng = random.Random(seed)
    cat_idx = [rng.randrange(len(CATEGORIAS)) for _ in range(n)]

    pesos = []
    temps = []
    for i in range(n):
        _, _, (wmin, wmax) = CATEGORIAS[cat_idx[i]]
        pesos.append(round(rng.uniform(wmin, wmax), 2))
        temps.append(temperatura_producto(cat_idx[i], rng, perfil_temperatura))

    carpeta = os.path.dirname(path)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{n} {capacidad}\n")
        for i in range(n):
            f.write(f"{pesos[i]} {temps[i]}\n")

        for i in range(n):
            fila = ["1.0"] * n
            for j in range(n):
                if i == j:
                    continue
                a, b = (i, j) if i < j else (j, i)
                clave = a * n + b
                entero = (clave * 6364136223846793005 + seed * 1442695040888963407) & ((1 << 64) - 1)
                entero = (entero * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
                r = (entero >> 11) / float(1 << 53)
                if cat_idx[i] == cat_idx[j]:
                    fila[j] = f"{0.7 + 0.3 * r:.2f}"
                else:
                    fila[j] = f"{0.3 * r:.2f}"
            f.write(" ".join(fila) + "\n")


def estimar_gib(n: int):
    valores = n * n
    bytes_promedio = 5.5
    return valores * bytes_promedio / (1024 ** 3)


def main():
    ap = argparse.ArgumentParser(description="Generador de instancias TP2")
    ap.add_argument("--n", type=int, required=True, help="cantidad de productos")
    ap.add_argument("--C", type=float, required=True, help="capacidad de cada vehiculo")
    ap.add_argument("--seed", type=int, default=0, help="semilla aleatoria")
    ap.add_argument("--perfil-temperatura", choices=["categorias", "fronteras"],
                    default="categorias", help="distribucion de temperaturas")
    ap.add_argument("--out", type=str, required=True, help="archivo de salida")
    args = ap.parse_args()

    if args.n >= 10000:
        estimado = estimar_gib(args.n)
        print(f"Instancia grande: generando matriz {args.n} x {args.n} "
              f"(aprox. {estimado:.1f} GiB)")
        escribir_grande(args.out, args.C, args.n, args.seed,
                        args.perfil_temperatura)
    else:
        pesos, temps, sim = generar(
            args.n, args.C, args.seed, args.perfil_temperatura
        )
        escribir(args.out, args.C, pesos, temps, sim)
    print(f"Instancia generada: {args.out}  (n={args.n}, C={args.C}, seed={args.seed})")


if __name__ == "__main__":
    main()
