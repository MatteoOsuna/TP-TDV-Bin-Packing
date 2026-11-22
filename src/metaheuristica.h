#ifndef METAHEURISTICA_H
#define METAHEURISTICA_H

#include <limits>

#include "instancia.h"
#include "solucion.h"
#include "temperatura.h"

struct ParamsMeta {
    double alpha = 1.0;
    double beta = 1.0;  // el main la reemplaza por la que se pidio (por defecto 1/S_max)
    double delta_temp = std::numeric_limits<double>::infinity();
    ModoTemp modo = ModoTemp::DELTA;
    int iteraciones = 1000;
    unsigned semilla = 42;

    // Parametros propios de GRASP:
    // Cantidad de mejores camiones candidatos entre los que se sortea en cada paso (RCL).
    // Con tam_rcl = 1 se comporta determinista (como FFD/BFD).
    int tam_rcl = 3;
};

Solucion metaheuristica(const Instancia& inst, const ParamsMeta& params);

#endif
