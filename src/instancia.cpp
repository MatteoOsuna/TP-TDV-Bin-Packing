#include "instancia.h"

#include <fstream>
#include <stdexcept>

Instancia Instancia::leer(const std::string& path) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("No se pudo abrir la instancia: " + path);
    }

    Instancia inst;
    if (!(in >> inst.n >> inst.capacidad)) {
        throw std::runtime_error("Error leyendo 'n' y 'C' en: " + path);
    }
    inst.peso.resize(inst.n);
    inst.temperatura.resize(inst.n);
    for (int i = 0; i < inst.n; ++i) {
        if (!(in >> inst.peso[i] >> inst.temperatura[i])) {
            throw std::runtime_error("Error leyendo peso/temperatura del producto " + std::to_string(i));
        }
    }

    inst.similitud.assign(inst.n, std::vector<double>(inst.n, 0.0));
    for (int i = 0; i < inst.n; ++i) {
        for (int j = 0; j < inst.n; ++j) {
            if (!(in >> inst.similitud[i][j])) {
                throw std::runtime_error("Error leyendo matriz de similitud en fila " + std::to_string(i));
            }
        }
    }

    return inst;
}
