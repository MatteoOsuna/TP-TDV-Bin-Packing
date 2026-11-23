#ifndef INSTANCIA_H
#define INSTANCIA_H

#include <string>
#include <vector>

// Datos de una instancia: n productos con peso, temperatura y similitudes.
struct Instancia {
    int n = 0;
    double capacidad = 0.0;                      // capacidad C de cada camion
    std::vector<double> peso;                    // peso[i]
    std::vector<double> temperatura;             // temperatura[i], en grados C
    std::vector<std::vector<double>> similitud;  // similitud[i][j], entre 0 y 1

    // Lee el archivo con el formato del enunciado.
    static Instancia leer(const std::string& path);

    double sim(int i, int j) const { return similitud[i][j]; }

    // Suma de las similitudes de todos los pares: la maxima similitud posible.
    double S_max() const {
        double total = 0.0;
        for (int i = 0; i < n; ++i)
            for (int j = i + 1; j < n; ++j) total += similitud[i][j];
        return total;
    }

    // beta = 1 / S_max normaliza la similitud a una contribucion maxima de 1.
    double beta_auto() const {
        double s = S_max();
        return s > 0.0 ? 1.0 / s : 0.0;
    }
};

#endif
