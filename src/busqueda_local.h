#ifndef BUSQUEDA_LOCAL_H
#define BUSQUEDA_LOCAL_H

#include <limits>

#include "instancia.h"
#include "solucion.h"
#include "temperatura.h"

// ===========================================================================
// TODO (grupo): BUSQUEDA LOCAL. El enunciado pide AL MENOS 2 operadores.
//
// Cada operador recibe una solucion factible, busca UN movimiento que mejore
// la funcion objetivo sin romper ninguna restriccion, lo aplica y devuelve
// true. Si no encuentra ninguno, deja la solucion como estaba y devuelve false.
//
// Todo movimiento tiene que respetar, en cada camion que toca:
//   - capacidad:   peso <= sol.inst->capacidad
//   - temperatura: temp_bin_ok(modo, tmin, tmax, delta_temp)   (temperatura.h)
// Para chequear la solucion entera: sol.es_factible(delta_temp, modo).
//
// Mejorar = que sol.objetivo(alpha, beta) baje. Con alpha = 1 y beta = 1/S_max
// eso es: menos camiones, o los mismos camiones con mas similitud.
// ===========================================================================

// Operador 1 (sugerido): RELOCATE. Mover un producto de su camion a otro.
// Si el camion de origen queda vacio, borrarlo de sol.bins para que K baje.
bool operador_relocate(Solucion& sol, double alpha, double beta,
                       double delta_temp = std::numeric_limits<double>::infinity(),
                       ModoTemp modo = ModoTemp::DELTA);

// Operador 2 (sugerido): SWAP. Intercambiar dos productos de camiones distintos.
// No cambia K: sirve para juntar mas similitud.
bool operador_swap(Solucion& sol, double alpha, double beta,
                   double delta_temp = std::numeric_limits<double>::infinity(),
                   ModoTemp modo = ModoTemp::DELTA);
// Operador 3: VACIAR CAMION. Intenta reubicar todos los productos de un camion
// en el resto de los camiones existentes para reducir K en 1 y mejorar el objetivo.
bool operador_vaciar_camion(Solucion& sol, double alpha, double beta,
                            double delta_temp = std::numeric_limits<double>::infinity(),
                            ModoTemp modo = ModoTemp::DELTA);

// Aplica los operadores mientras alguno mejore (hasta llegar a un optimo local).
Solucion busqueda_local(Solucion inicial, double alpha, double beta,
                        double delta_temp = std::numeric_limits<double>::infinity(),
                        ModoTemp modo = ModoTemp::DELTA);

#endif
