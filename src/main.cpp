#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <ctime>
#include <filesystem>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

#include "busqueda_local.h"
#include "constructivas.h"
#include "instancia.h"
#include "metaheuristica.h"
#include "solucion.h"
#include "temperatura.h"

namespace fs = std::filesystem;

// Uso:
//   tp2                                    -> modo interactivo con menus
//   tp2 <input> <output> [metodo] [alpha] [beta] [delta] [modo] [iteraciones] [semilla]
//      metodo: bfd | mochila | costo | meta | ffd  (default bfd)
//      alpha:  default 1
//      beta:   numero o "auto" = 1/S_max (default auto)
//      delta:  tolerancia de temperatura en grados (default sin limite)
//      modo:   delta | bandas | hibrido (default delta)
//      iteraciones, semilla: solo para "meta" (default 1000 y 42)

const double INF = std::numeric_limits<double>::infinity();

// Valores fijos del modo interactivo (los elegidos para el modelo).
// beta no esta aca porque depende de la instancia: beta = 1 / S_max.
const double ALPHA_FIJO = 1.0;
const double DELTA_FIJO = 6.0;  // tolerancia de temperatura, en grados

static Solucion resolver(const Instancia& inst, const std::string& metodo,
                         double alpha, double beta, double delta, ModoTemp modo,
                         int iteraciones = 1000, unsigned semilla = 42) {
    if (metodo == "bfd") return constructiva_best_fit(inst, alpha, beta, delta, modo);
    if (metodo == "mochila") return constructiva_mochila(inst, alpha, beta, delta, modo);
    if (metodo == "costo") return constructiva_costo(inst, alpha, beta, delta, modo);
    if (metodo == "ffd") return constructiva_first_fit(inst, alpha, beta, delta, modo);
    if (metodo == "meta") {
        ParamsMeta params;
        params.alpha = alpha;
        params.beta = beta;
        params.delta_temp = delta;
        params.modo = modo;
        params.iteraciones = iteraciones;
        params.semilla = semilla;
        return metaheuristica(inst, params);
    }
    throw std::runtime_error("Metodo desconocido: " + metodo + " (use bfd | mochila | costo | meta | ffd)");
}

static std::string leer_linea(const std::string& prompt) {
    std::cout << prompt << std::flush;
    std::string s;
    if (!std::getline(std::cin, s)) {
        std::cout << "\nEntrada terminada.\n";
        std::exit(1);
    }
    return s;
}

// Muestra opciones numeradas y devuelve el indice elegido (desde 0).
static int elegir(const std::string& titulo, const std::vector<std::string>& opciones) {
    std::cout << "\n" << titulo << "\n";
    for (size_t k = 0; k < opciones.size(); ++k)
        std::cout << "  [" << k + 1 << "] " << opciones[k] << "\n";
    while (true) {
        std::string s = leer_linea("Elegi una opcion: ");
        try {
            int v = std::stoi(s);
            if (v >= 1 && v <= static_cast<int>(opciones.size())) return v - 1;
        } catch (...) {
        }
        std::cout << "  Opcion invalida, proba de nuevo.\n";
    }
}

// Orden natural: n10 < n20 < n100.
static bool menor_natural(const std::string& a, const std::string& b) {
    size_t i = 0, j = 0;
    while (i < a.size() && j < b.size()) {
        if (std::isdigit(static_cast<unsigned char>(a[i])) &&
            std::isdigit(static_cast<unsigned char>(b[j]))) {
            size_t i2 = i, j2 = j;
            while (i2 < a.size() && std::isdigit(static_cast<unsigned char>(a[i2]))) ++i2;
            while (j2 < b.size() && std::isdigit(static_cast<unsigned char>(b[j2]))) ++j2;
            long long na = std::stoll(a.substr(i, i2 - i));
            long long nb = std::stoll(b.substr(j, j2 - j));
            if (na != nb) return na < nb;
            i = i2;
            j = j2;
        } else {
            if (a[i] != b[j]) return a[i] < b[j];
            ++i;
            ++j;
        }
    }
    return a.size() < b.size();
}

// Todos los .txt de instancias/ (con subcarpetas).
static std::vector<std::string> listar_instancias() {
    std::vector<std::string> res;
    if (!fs::exists("instancias")) return res;
    for (const auto& e : fs::recursive_directory_iterator("instancias"))
        if (e.is_regular_file() && e.path().extension() == ".txt")
            res.push_back(e.path().generic_string());
    std::sort(res.begin(), res.end(), menor_natural);
    return res;
}

// Corre un script de Python; si "python" falla, prueba con el lanzador "py".
static bool correr_python(const std::string& args_script) {
    for (const std::string interprete : {"python", "py -3"}) {
        if (std::system((interprete + args_script).c_str()) == 0) return true;
        std::cout << "  (no funciono con \"" << interprete << "\")\n" << std::flush;
    }
    return false;
}

// "auto" o vacio -> 1/S_max de la instancia; si no, el numero escrito.
static double beta_desde_texto(const std::string& s, const Instancia& inst, bool& es_auto) {
    es_auto = s.empty() || s == "auto";
    if (es_auto) return inst.beta_auto();
    try {
        return std::stod(s);
    } catch (...) {
        throw std::runtime_error("beta invalido: " + s + " (use un numero o 'auto')");
    }
}

// Crea resultados/solucion_AAAA-MM-DD_HH-MM-SS (con la hora actual) y devuelve su ruta.
// Si ya existe una carpeta con ese nombre (dos corridas en el mismo segundo), agrega _2, _3...
static std::string carpeta_de_corrida() {
    std::time_t ahora = std::time(nullptr);
    char marca[32];
    std::strftime(marca, sizeof(marca), "%Y-%m-%d_%H-%M-%S", std::localtime(&ahora));
    std::string carpeta = std::string("resultados/solucion_") + marca;
    for (int extra = 2; fs::exists(carpeta); ++extra)
        carpeta = std::string("resultados/solucion_") + marca + "_" + std::to_string(extra);
    fs::create_directories(carpeta);
    return carpeta;
}

static std::string texto_delta(double d) {
    if (d == INF) return "inf";
    std::string s = std::to_string(d);
    s.erase(s.find_last_not_of('0') + 1);
    if (!s.empty() && s.back() == '.') s.pop_back();
    return s;
}

static int modo_interactivo() {
    std::cout << "==============================================\n"
              << "  TP2 - Armado de cargas (Bin Packing)\n"
              << "==============================================\n";

    const std::vector<std::string> codigos = {"bfd", "mochila", "costo"};
    const std::vector<std::string> nombres = {"BFD", "MOCHILA", "COSTO"};
    int h = elegir("Que heuristica queres correr?",
                   {"BFD     - de mayor a menor peso, al camion mas lleno donde entra",
                    "MOCHILA - un camion por vez, empezando por el producto mas pesado",
                    "COSTO   - al camion donde menos empeora la funcion objetivo"});

    std::vector<std::string> instancias = listar_instancias();
    if (instancias.empty()) {
        std::cout << "No encontre instancias en la carpeta instancias/.\n";
        return 1;
    }
    int ii = elegir("Que instancia queres resolver?", instancias);
    const std::string path_in = instancias[ii];

    const std::string d = texto_delta(DELTA_FIJO);
    int t = elegir("Restriccion de temperatura (delta fijo = " + d + " grados):",
                   {"Sin restriccion",
                    "Delta relativo  (max(t) - min(t) <= " + d + " en cada camion)",
                    "Bandas fijas    (congelado / refrigerado / ambiente / caliente)",
                    "Hibrido         (setpoint de la heladera a <= " + d + " grados de todos)"});
    ModoTemp modo = ModoTemp::DELTA;
    double delta = INF;
    if (t == 1) {
        modo = ModoTemp::DELTA;
        delta = DELTA_FIJO;
    } else if (t == 2) {
        modo = ModoTemp::BANDAS;
    } else if (t == 3) {
        modo = ModoTemp::HIBRIDO;
        delta = DELTA_FIJO;
    }

    const double alpha = ALPHA_FIJO;
    const std::string beta_txt = "auto";

    int vista = elegir("Como queres ver la construccion?",
                       {"Ventana animada (grafo + vecindario de cada paso)",
                        "Texto en la consola (paso a paso)",
                        "No mostrar, solo el resultado"});

    // Cada corrida guarda sus tres archivos en su propia carpeta.
    const std::string carpeta = carpeta_de_corrida();
    const std::string stem = fs::path(path_in).stem().string();
    const std::string base = carpeta + "/" + nombres[h] + "_" + stem;
    const std::string path_out = base + ".out";
    const std::string path_png = base + ".png";
    const std::string path_traza = base + ".traza";
    const std::string modo_txt = (t == 0 ? std::string("ninguno") : nombre_modo(modo));

    set_traza_consola(vista == 1);
    set_traza_archivo(path_traza);

    Instancia inst = Instancia::leer(path_in);
    bool beta_es_auto = false;
    const double beta = beta_desde_texto(beta_txt, inst, beta_es_auto);

    std::cout << "\n----------------------------------------------\n"
              << "  Heuristica : " << nombres[h] << "\n"
              << "  Instancia  : " << path_in << "  (n = " << inst.n
              << " productos, capacidad = " << inst.capacidad << ")\n"
              << "  Temperatura: "
              << (t == 0 ? std::string("sin restriccion")
                         : nombre_modo(modo) + (modo == ModoTemp::BANDAS ? "" : " (delta = " + texto_delta(delta) + ")"))
              << "\n"
              << "  alpha = " << alpha << ", beta = " << beta;
    if (beta_es_auto) std::cout << "  (auto: 1/S_max, con S_max = " << inst.S_max() << ")";
    std::cout << "\n----------------------------------------------\n";

    Solucion sol = resolver(inst, codigos[h], alpha, beta, delta, modo);
    sol.escribir(path_out);

    std::cout << "\n=== Resultado ===\n"
              << "  Camiones (K): " << sol.K() << "\n"
              << "  Objetivo    : " << sol.objetivo(alpha, beta) << "\n"
              << "  Factible    : " << (sol.es_factible(delta, modo) ? "si" : "NO") << "\n"
              << "  Carpeta     : " << carpeta << "/\n";

    // Grafico de la solucion.
    const std::string args_script = " experimentacion/graficar_solucion.py"
                                    " --inst \"" + path_in + "\""
                                    " --sol \"" + path_out + "\""
                                    " --heuristica " + nombres[h] +
                                    " --alpha " + std::to_string(alpha) +
                                    " --beta " + (beta_es_auto ? std::string("auto") : std::to_string(beta)) +
                                    " --delta " + texto_delta(delta) +
                                    " --modo " + modo_txt +
                                    " --out \"" + path_png + "\"";

    std::cout << "\nGenerando grafico...\n" << std::flush;
    if (!correr_python(args_script))
        std::cout << "  No se pudo generar el grafico. Instala matplotlib en el Python de esta\n"
                  << "  terminal con:  python -m pip install matplotlib\n";

    // Ventana animada.
    if (vista == 0) {
        const std::string args_ventana = " experimentacion/ver_construccion.py"
                                         " --inst \"" + path_in + "\""
                                         " --traza \"" + path_traza + "\""
                                         " --heuristica " + nombres[h] +
                                         " --delta " + texto_delta(delta) +
                                         " --modo " + modo_txt;
        std::cout << "\nAbriendo la ventana animada (cerrala cuando termines)...\n" << std::flush;
        if (!correr_python(args_ventana))
            std::cout << "  No se pudo abrir la ventana. Instala las librerias con:\n"
                      << "  python -m pip install matplotlib networkx\n";
    }

    leer_linea("\nApreta Enter para salir...");
    return 0;
}

static int modo_cli(int argc, char** argv) {
    const std::string path_in = argv[1];
    const std::string path_out = argv[2];
    const std::string metodo = (argc > 3) ? argv[3] : "bfd";
    const double alpha = (argc > 4) ? std::atof(argv[4]) : 1.0;
    const double delta = (argc > 6) ? std::atof(argv[6]) : INF;
    const ModoTemp modo = (argc > 7) ? parse_modo_temp(argv[7]) : ModoTemp::DELTA;
    const int iteraciones = (argc > 8) ? std::atoi(argv[8]) : 1000;
    const unsigned semilla = (argc > 9) ? static_cast<unsigned>(std::atoi(argv[9])) : 42u;

    Instancia inst = Instancia::leer(path_in);
    bool beta_es_auto = false;
    const double beta = beta_desde_texto((argc > 5) ? argv[5] : "auto", inst, beta_es_auto);
    Solucion sol = resolver(inst, metodo, alpha, beta, delta, modo, iteraciones, semilla);

    if (!sol.es_factible(delta, modo))
        std::cerr << "ADVERTENCIA: la solucion generada no es factible.\n";

    sol.escribir(path_out);

    std::cerr << "Metodo: " << metodo << " | modo: " << nombre_modo(modo)
              << " | K = " << sol.K()
              << " | objetivo = " << sol.objetivo(alpha, beta) << '\n';
    return 0;
}

int main(int argc, char** argv) {
    try {
        if (argc == 1) return modo_interactivo();
        if (argc < 3) {
            std::cerr << "Uso:\n"
                      << "  " << argv[0] << "                (modo interactivo con menus)\n"
                      << "  " << argv[0] << " <input> <output> [metodo=bfd|mochila|costo|meta|ffd]"
                      << " [alpha] [beta] [delta] [modo=delta|bandas|hibrido]"
                      << " [iteraciones] [semilla]\n";
            return 1;
        }
        return modo_cli(argc, argv);
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << '\n';
        return 1;
    }
}
