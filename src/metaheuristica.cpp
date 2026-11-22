#include "metaheuristica.h"

#include <algorithm>
#include <limits>
#include <numeric>
#include <random>
#include <utility>
#include <vector>

#include "busqueda_local.h"
#include "constructivas.h"

namespace {

bool entra_en_bin(const Instancia& inst, const std::vector<int>& bin, int item,
                  double delta_temp, ModoTemp modo) {
    double peso = inst.peso[item];
    double tmin = inst.temperatura[item];
    double tmax = tmin;

    for (int k : bin) {
        peso += inst.peso[k];
        tmin = std::min(tmin, inst.temperatura[k]);
        tmax = std::max(tmax, inst.temperatura[k]);
    }

    return peso <= inst.capacidad + 1e-9 && temp_bin_ok(modo, tmin, tmax, delta_temp);
}

double ganancia_similitud(const Instancia& inst, const std::vector<int>& bin, int item) {
    double suma = 0.0;
    for (int k : bin) {
        suma += inst.sim(item, k);
    }
    return suma;
}

Solucion construir_grasp_ffd(const Instancia& inst, double beta,
                             double delta_temp, ModoTemp modo,
                             int tam_rcl, std::mt19937& rng) {
    const int n = static_cast<int>(inst.peso.size());
    std::vector<int> orden(n);
    std::iota(orden.begin(), orden.end(), 0);

    // Orden decreciente por peso (criterio FFD)
    std::sort(orden.begin(), orden.end(), [&](int a, int b) {
        if (inst.peso[a] != inst.peso[b]) return inst.peso[a] > inst.peso[b];
        return a < b;
    });

    Solucion sol;
    sol.inst = &inst;

    const int k_rcl = std::max(1, tam_rcl);

    for (int item : orden) {
        struct Candidato {
            int bin_idx;
            double score;
        };
        std::vector<Candidato> candidatos;

        for (int b = 0; b < sol.K(); ++b) {
            if (entra_en_bin(inst, sol.bins[b], item, delta_temp, modo)) {
                double score = beta * ganancia_similitud(inst, sol.bins[b], item);
                candidatos.push_back({b, score});
            }
        }

        if (candidatos.empty()) {
            sol.bins.push_back({item});
        } else {
            // Ordenar candidatos de mayor a menor aporte de similitud
            std::sort(candidatos.begin(), candidatos.end(), [](const Candidato& x, const Candidato& y) {
                if (x.score != y.score) return x.score > y.score;
                return x.bin_idx < y.bin_idx;
            });

            int limite = std::min(k_rcl, static_cast<int>(candidatos.size()));
            std::uniform_int_distribution<int> dist(0, limite - 1);
            int elegido = candidatos[dist(rng)].bin_idx;
            sol.bins[elegido].push_back(item);
        }
    }

    return sol;
}

}  // namespace

Solucion metaheuristica(const Instancia& inst, const ParamsMeta& params) {
    std::mt19937 rng(params.semilla);

    // Solucion base determinista + busqueda local como cota inicial segura
    Solucion mejor = constructiva_first_fit(inst, params.alpha, params.beta,
                                            params.delta_temp, params.modo);
    mejor = busqueda_local(std::move(mejor), params.alpha, params.beta,
                           params.delta_temp, params.modo);

    bool tiene_mejor = mejor.es_factible(params.delta_temp, params.modo);
    double mejor_obj = tiene_mejor ? mejor.objetivo(params.alpha, params.beta)
                                   : std::numeric_limits<double>::infinity();

    for (int it = 0; it < params.iteraciones; ++it) {
        Solucion actual = construir_grasp_ffd(inst, params.beta,
                                              params.delta_temp, params.modo,
                                              params.tam_rcl, rng);
        actual = busqueda_local(std::move(actual), params.alpha, params.beta,
                                params.delta_temp, params.modo);

        if (!actual.es_factible(params.delta_temp, params.modo)) {
            continue;
        }

        double obj = actual.objetivo(params.alpha, params.beta);
        if (!tiene_mejor || obj < mejor_obj - 1e-12) {
            mejor_obj = obj;
            mejor = std::move(actual);
            tiene_mejor = true;
        }
    }

    return mejor;
}
