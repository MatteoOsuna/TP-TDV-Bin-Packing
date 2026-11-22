#include "busqueda_local.h"

#include <algorithm>
#include <utility>

// ---------------------------------------------------------------------------
// Auxiliares de RELOCATE
// ---------------------------------------------------------------------------

// ¿Entra el producto i en 'bin' por peso y por temperatura?
// (i NO esta en 'bin': se prueba el camion como quedaria con i agregado.)
static bool entra_en(const Instancia& inst, const std::vector<int>& bin, int i,
                     double delta_temp, ModoTemp modo) {
    double peso = inst.peso[i];
    double tmin = inst.temperatura[i];
    double tmax = tmin;
    for (int j : bin) {
        peso += inst.peso[j];
        tmin = std::min(tmin, inst.temperatura[j]);
        tmax = std::max(tmax, inst.temperatura[j]);
    }
    return peso <= inst.capacidad + 1e-9 && temp_bin_ok(modo, tmin, tmax, delta_temp);
}

// Suma de similitudes de i con los demas productos de 'bin' (sin contarse a si mismo).
static double similitud_con(const Instancia& inst, const std::vector<int>& bin, int i) {
    double total = 0.0;
    for (int j : bin)
        if (j != i) total += inst.sim(i, j);
    return total;
}

// RELOCATE (mejor mejora): evalua todos los movimientos "producto i del camion a
// al camion b" y aplica el que mas baja el objetivo.
//   cambio = -alpha * vacia - beta * (ganancia - perdida)
// Sacar un producto de un camion nunca rompe capacidad ni temperatura (el rango
// de temperaturas solo se achica), asi que solo se chequea el camion destino.
bool operador_relocate(Solucion& sol, double alpha, double beta,
                       double delta_temp, ModoTemp modo) {
    const Instancia& inst = *sol.inst;
    double mejor_cambio = -1e-12;  // solo se acepta una mejora real
    int mejor_a = -1, mejor_pos = -1, mejor_b = -1;

    for (int a = 0; a < sol.K(); ++a) {
        const std::vector<int>& bin_a = sol.bins[a];
        const double vacia = (bin_a.size() == 1) ? 1.0 : 0.0;
        for (size_t pos = 0; pos < bin_a.size(); ++pos) {
            const int i = bin_a[pos];
            const double perdida = similitud_con(inst, bin_a, i);
            for (int b = 0; b < sol.K(); ++b) {
                if (b == a) continue;
                if (!entra_en(inst, sol.bins[b], i, delta_temp, modo)) continue;
                const double ganancia = similitud_con(inst, sol.bins[b], i);
                const double cambio = -alpha * vacia - beta * (ganancia - perdida);
                if (cambio < mejor_cambio) {
                    mejor_cambio = cambio;
                    mejor_a = a;
                    mejor_pos = static_cast<int>(pos);
                    mejor_b = b;
                }
            }
        }
    }

    if (mejor_a < 0) return false;  // ningun movimiento mejora: optimo local

    const int i = sol.bins[mejor_a][mejor_pos];
    sol.bins[mejor_a].erase(sol.bins[mejor_a].begin() + mejor_pos);
    sol.bins[mejor_b].push_back(i);
    if (sol.bins[mejor_a].empty()) sol.bins.erase(sol.bins.begin() + mejor_a);  // K baja
    return true;
}

bool operador_swap(Solucion& sol, double alpha, double beta,
                   double delta_temp, ModoTemp modo) {
    (void)alpha;

    const int num_bins = sol.K();
    const double cap = sol.inst->capacidad;
    const double eps = 1e-9;
    const double inf = std::numeric_limits<double>::infinity();

    auto eval_bin_sin_saliente_con_entrante = [&](int bin_idx, size_t idx_saliente,
                                                  int item_entrante, double& peso_out,
                                                  double& tmin_out, double& tmax_out,
                                                  double& delta_sim_out) {
        const auto& bin = sol.bins[bin_idx];
        const int item_saliente = bin[idx_saliente];

        peso_out = 0.0;
        tmin_out = inf;
        tmax_out = -inf;
        delta_sim_out = 0.0;

        for (size_t idx_k = 0; idx_k < bin.size(); ++idx_k) {
            if (idx_k == idx_saliente) continue;
            int k = bin[idx_k];
            peso_out += sol.inst->peso[k];
            tmin_out = std::min(tmin_out, sol.inst->temperatura[k]);
            tmax_out = std::max(tmax_out, sol.inst->temperatura[k]);
            delta_sim_out += -sol.inst->sim(item_saliente, k) + sol.inst->sim(item_entrante, k);
        }

        peso_out += sol.inst->peso[item_entrante];
        tmin_out = std::min(tmin_out, sol.inst->temperatura[item_entrante]);
        tmax_out = std::max(tmax_out, sol.inst->temperatura[item_entrante]);
    };

    for (int a = 0; a < num_bins; ++a) {
        for (int b = a + 1; b < num_bins; ++b) {
            for (size_t idx_i = 0; idx_i < sol.bins[a].size(); ++idx_i) {
                int i = sol.bins[a][idx_i];

                for (size_t idx_j = 0; idx_j < sol.bins[b].size(); ++idx_j) {
                    int j = sol.bins[b][idx_j];

                    double peso_a = 0.0, tmin_a = inf, tmax_a = -inf, delta_a = 0.0;
                    double peso_b = 0.0, tmin_b = inf, tmax_b = -inf, delta_b = 0.0;

                    eval_bin_sin_saliente_con_entrante(a, idx_i, j, peso_a, tmin_a, tmax_a, delta_a);
                    if (peso_a > cap + eps) continue;
                    if (!temp_bin_ok(modo, tmin_a, tmax_a, delta_temp)) continue;

                    eval_bin_sin_saliente_con_entrante(b, idx_j, i, peso_b, tmin_b, tmax_b, delta_b);
                    if (peso_b > cap + eps) continue;
                    if (!temp_bin_ok(modo, tmin_b, tmax_b, delta_temp)) continue;

                    double cambio = -beta * (delta_a + delta_b);
                    if (cambio < -eps) {
                        sol.bins[a][idx_i] = j;
                        sol.bins[b][idx_j] = i;
                        return true;
                    }
                }
            }
        }
    }

    return false;
}

Solucion busqueda_local(Solucion inicial, double alpha, double beta,
                        double delta_temp, ModoTemp modo) {
    Solucion actual = std::move(inicial);
    bool mejoro = true;
    while (mejoro) {
        mejoro = false;
        if (operador_relocate(actual, alpha, beta, delta_temp, modo)) mejoro = true;
        if (operador_swap(actual, alpha, beta, delta_temp, modo)) mejoro = true;
    }
    return actual;
}
