"""
graficos_binarios.py
--------------------
Genera gráficas de desviación de COP y VHC respecto al propano, y gráficas
de variables de diagnóstico (glide_0, glide_k, p_0, p_k, t_descarga) para
mezclas binarias. Calcula el ciclo al vuelo; no itera sobre resultados guardados.

Todas las gráficas muestran dos series:
  - Todos los puntos sin error de REFPROP  (línea azul)
  - Puntos que además pasan el filtro de calidad (línea verde)

Salida:
    graficos_binarios/[water_config]/[fluid_A]_[fluid_B]/COP.png
    graficos_binarios/[water_config]/[fluid_A]_[fluid_B]/VHC.png
    graficos_binarios/[water_config]/[fluid_A]_[fluid_B]/glide_0.png
    graficos_binarios/[water_config]/[fluid_A]_[fluid_B]/glide_k.png
    graficos_binarios/[water_config]/[fluid_A]_[fluid_B]/p_0.png
    graficos_binarios/[water_config]/[fluid_A]_[fluid_B]/p_k.png
    graficos_binarios/[water_config]/[fluid_A]_[fluid_B]/t_descarga.png

Uso típico:
    from graficos_binarios import generar_graficos

    generar_graficos(
        mezclas=[("PROPANE", "DME"), ("PROPANE", "ISOBUTANE")],
        water_config="alta",
        n_puntos=41,
    )
"""

from __future__ import annotations

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

from refprop_utils import init_refprop
from ciclo_binario import calcular_ciclo_basico, calcular_valores_referencia

ASHRAE_NAMES = {
    "DME":       "RE170",
    "PROPYLENE": "R1270",
    "PROPANE":   "R290",
    "CO2":       "CO2",
    "BUTANE":    "R600",
    "ISOBUTANE": "R600a",
    "METHANE":   "R50",
    "ETHANE":    "R170",
    "ETHYLENE":  "R1150",
}

# ---------------------------------------------------------------------------
# Criterios de filtrado (mismos que filtrar() en ciclo_basico.py)
# ---------------------------------------------------------------------------

def _pasa_filtro(row: dict, vhc_min: float, vhc_max: float) -> bool:
    return (
        row["error"] is None
        and vhc_min <= row["VHC"] <= vhc_max
        and row["t_2"] < 130
        and row["p_2"] < 28
        and row["glide_k"] < 10
        and row["glide_0"] < 10
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nombre_carpeta(fluid_a: str, fluid_b: str) -> str:
    a = ASHRAE_NAMES.get(fluid_a, fluid_a)
    b = ASHRAE_NAMES.get(fluid_b, fluid_b)
    return f"{a}_{b}".replace("/", "-")


# ---------------------------------------------------------------------------
# Cálculo de datos para una mezcla
# ---------------------------------------------------------------------------

def calcular_datos_mezcla(
    fluid_a: str,
    fluid_b: str,
    water_config: str,
    n_puntos: int,
    vhc_min: float,
    vhc_max: float,
) -> dict[str, list]:
    """
    Devuelve un dict con dos conjuntos de series:
      'todos'    -> puntos sin error de REFPROP
      'filtrado' -> puntos que además pasan el filtro de calidad

    Cada conjunto es un dict: {x, cop, vhc, glide_0, glide_k, p_0, p_k, t_desc}
    """
    todos    = {k: [] for k in ("x", "cop", "vhc", "glide_0", "glide_k", "p_0", "p_k", "t_desc")}
    filtrado = {k: [] for k in ("x", "cop", "vhc", "glide_0", "glide_k", "p_0", "p_k", "t_desc")}

    for x_a in np.linspace(0, 1, n_puntos):
        row = calcular_ciclo_basico(fluid_a, fluid_b, float(x_a), water_config)
        if row["error"] is not None:
            continue

        vals = {
            "x":       row["x_A"],
            "cop":     row["COP"],
            "vhc":     row["VHC"],
            "glide_0": row["glide_0"],
            "glide_k": row["glide_k"],
            "p_0":     row["p_1"],   # presión en el evaporador (punto 1)
            "p_k":     row["p_2"],   # presión en el condensador (punto 2)
            "t_desc":  row["t_2"],   # temperatura de descarga (punto 2)
        }

        for k, v in vals.items():
            todos[k].append(v)

        if _pasa_filtro(row, vhc_min, vhc_max):
            for k, v in vals.items():
                filtrado[k].append(v)

    return {"todos": todos, "filtrado": filtrado}


# ---------------------------------------------------------------------------
# Graficado
# ---------------------------------------------------------------------------

# Paleta por water_config: (color_todos, color_filtrado)
_PALETA: dict[str, tuple[str, str]] = {
    "media": ("#93C5FD", "#1D4ED8"),  # azul
    "alta":  ("#86EFAC", "#15803D"),  # verde
}
# Para configs que no son "media-alta", usar azul por defecto
_COLOR_DEFAULT = ("#93C5FD", "#1D4ED8")


def _estilos(cfg: str, multi: bool) -> tuple[dict, dict]:
    """Devuelve (style_todos, style_filt) para un config dado."""
    c_todos, c_filt = _PALETA.get(cfg, _COLOR_DEFAULT)
    sufijo = f" ({cfg})" if multi else ""
    style_t = dict(
        color=c_todos, linewidth=1.5, marker="o", markersize=3,
        markerfacecolor=c_todos, label=f"Todos los puntos{sufijo}",
    )
    style_f = dict(
        color=c_filt, linewidth=1.8, marker="o", markersize=3.5,
        markerfacecolor=c_filt, label=f"Cumplen las restricciones{sufijo}",
    )
    return style_t, style_f


def _quitar_outliers(xs: list, ys: list, n_sigma: float = 3.0):
    """
    Elimina puntos aislados cuyo salto con ambos vecinos supera
    media_saltos + n_sigma * std_saltos.
    """
    if len(ys) < 3:
        return xs, ys
    saltos = [abs(ys[i] - ys[i - 1]) for i in range(1, len(ys))]
    umbral = np.mean(saltos) + n_sigma * np.std(saltos)
    xs_ok, ys_ok = [xs[0]], [ys[0]]
    for i in range(1, len(ys) - 1):
        salto_ant = abs(ys[i] - ys[i - 1])
        salto_sig = abs(ys[i] - ys[i + 1])
        if salto_ant > umbral and salto_sig > umbral:
            continue  # pico/valle aislado: se descarta
        xs_ok.append(xs[i])
        ys_ok.append(ys[i])
    xs_ok.append(xs[-1])
    ys_ok.append(ys[-1])
    return xs_ok, ys_ok


def _plot_desviacion(
    datos_por_config: dict[str, dict],
    clave: str,
    refs: dict[str, float],
    titulo: str,
    xlabel: str,
    ylabel: str,
    ruta: str,
    limites_pct: tuple[float, float] | None = None,
) -> None:
    """Gráfica de desviación porcentual respecto a un valor de referencia."""

    def pct(vals, ref):
        return [((v - ref) / ref) * 100 for v in vals]

    multi = len(datos_por_config) > 1
    fig, ax = plt.subplots(figsize=(10, 6))

    for cfg, datos in datos_por_config.items():
        ref = refs[cfg]
        style_t, style_f = _estilos(cfg, multi)
        todos    = datos["todos"]
        filtrado = datos["filtrado"]
        if todos[clave]:
            tx, ty = _quitar_outliers(todos["x"], pct(todos[clave], ref))
            ax.plot(tx, ty, **style_t)
        if filtrado[clave]:
            fx, fy = _quitar_outliers(filtrado["x"], pct(filtrado[clave], ref))
            ax.plot(fx, fy, **style_f)

    ax.axhline(y=0, color="#DC2626", linewidth=1.2, linestyle="--", label="Referencia R290")

    if limites_pct is not None:
        lo, hi = limites_pct
        y_min, y_max = ax.get_ylim()
        primer_label = True
        for val in (hi, lo):
            if y_min <= val <= y_max:
                label = "Rango VHC ±30%" if primer_label else "_nolegend_"
                ax.axhline(y=val, color="#EAB308", linewidth=1.2, linestyle="--", label=label)
                primer_label = False

    ax.set_xlim(0, 1)
    ax.set_xticks([i / 10 for i in range(11)])
    ax.set_xticklabels([f"{i * 10}%" for i in range(11)])
    ax.yaxis.set_major_formatter(
        mtick.FuncFormatter(lambda v, _: f"{v:.0f}%" if v == int(v) else f"{v:.1f}%")
    )

    ax.set_title(titulo, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(True, linestyle=":", alpha=0.55)
    ax.legend(fontsize=10)

    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def _plot_absoluto(
    datos_por_config: dict[str, dict],
    clave: str,
    titulo: str,
    xlabel: str,
    ylabel: str,
    limite_h: float | None,
    ruta: str,
) -> None:
    """Gráfica de valor absoluto con línea de límite opcional."""

    multi = len(datos_por_config) > 1
    fig, ax = plt.subplots(figsize=(10, 6))

    for cfg, datos in datos_por_config.items():
        style_t, style_f = _estilos(cfg, multi)
        todos    = datos["todos"]
        filtrado = datos["filtrado"]
        if todos[clave]:
            tx, ty = _quitar_outliers(todos["x"], todos[clave])
            ax.plot(tx, ty, **style_t)
        if filtrado[clave]:
            fx, fy = _quitar_outliers(filtrado["x"], filtrado[clave])
            ax.plot(fx, fy, **style_f)

    if limite_h is not None:
        ax.axhline(
            y=limite_h, color="#DC2626", linewidth=1.2, linestyle="--",
            label=f"Límite ({limite_h})",
        )

    ax.set_xlim(0, 1)
    ax.set_xticks([i / 10 for i in range(11)])
    ax.set_xticklabels([f"{i * 10}%" for i in range(11)])

    ax.set_title(titulo, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(True, linestyle=":", alpha=0.55)
    ax.legend(fontsize=10)

    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def graficar_mezcla(
    fluid_a: str,
    fluid_b: str,
    water_config: str,
    refs_por_config: dict[str, dict],
    n_puntos: int,
) -> None:
    configs = ["media", "alta"] if water_config == "media-alta" else [water_config]

    print(f"  Calculando {fluid_a} / {fluid_b} …")

    datos_por_config: dict[str, dict] = {}
    for cfg in configs:
        r = refs_por_config[cfg]
        datos_por_config[cfg] = calcular_datos_mezcla(
            fluid_a, fluid_b, cfg, n_puntos, r["vhc_min"], r["vhc_max"]
        )

    if all(not d["todos"]["x"] for d in datos_por_config.values()):
        print(f"  ⚠ Sin resultados válidos para {fluid_a}/{fluid_b}, se omite.")
        return

    carpeta = os.path.join(
        "graficos_binarios",
        water_config,
        _nombre_carpeta(fluid_a, fluid_b),
    )
    os.makedirs(carpeta, exist_ok=True)

    xlabel = f"Fracción másica de {ASHRAE_NAMES.get(fluid_a, fluid_a)}"
    nombre = f"{ASHRAE_NAMES.get(fluid_a, fluid_a)} / {ASHRAE_NAMES.get(fluid_b, fluid_b)}"

    _plot_desviacion(
        datos_por_config, "cop",
        refs={cfg: refs_por_config[cfg]["cop_ref"] for cfg in configs},
        titulo=f"Δ COP: {nombre}",
        xlabel=xlabel,
        ylabel="Δ COP respecto a R290",
        ruta=os.path.join(carpeta, "COP.png"),
    )

    _plot_desviacion(
        datos_por_config, "vhc",
        refs={cfg: refs_por_config[cfg]["vhc_ref"] for cfg in configs},
        titulo=f"Δ VHC: {nombre}",
        xlabel=xlabel,
        ylabel="Δ VHC respecto a R290",
        ruta=os.path.join(carpeta, "VHC.png"),
        limites_pct=(-30.0, 30.0),
    )

    _plot_absoluto(
        datos_por_config, "glide_0",
        titulo=f"Glide en el evaporador: {nombre}",
        xlabel=xlabel,
        ylabel="Glide evaporador (K)",
        limite_h=10.0,
        ruta=os.path.join(carpeta, "glide_0.png"),
    )

    _plot_absoluto(
        datos_por_config, "glide_k",
        titulo=f"Glide en el condensador: {nombre}",
        xlabel=xlabel,
        ylabel="Glide condensador (K)",
        limite_h=10.0,
        ruta=os.path.join(carpeta, "glide_k.png"),
    )

    _plot_absoluto(
        datos_por_config, "p_0",
        titulo=f"Presión en el evaporador: {nombre}",
        xlabel=xlabel,
        ylabel="Presión evaporador (bar)",
        limite_h=None,
        ruta=os.path.join(carpeta, "p_0.png"),
    )

    _plot_absoluto(
        datos_por_config, "p_k",
        titulo=f"Presión en el condensador: {nombre}",
        xlabel=xlabel,
        ylabel="Presión condensador (bar)",
        limite_h=28.0,
        ruta=os.path.join(carpeta, "p_k.png"),
    )

    _plot_absoluto(
        datos_por_config, "t_desc",
        titulo=f"Temperatura de descarga: {nombre}",
        xlabel=xlabel,
        ylabel="T descarga (°C)",
        limite_h=130.0,
        ruta=os.path.join(carpeta, "t_descarga.png"),
    )

    print(f"  ✓ Guardado en {carpeta}/")


# ---------------------------------------------------------------------------
# Función principal pública
# ---------------------------------------------------------------------------

def generar_graficos(
    mezclas: list[tuple[str, str]],
    water_config: str,
    n_puntos: int = 41,
) -> None:
    """
    Calcula y grafica COP, VHC y variables de diagnóstico para cada par de fluidos.

    Parámetros
    ----------
    mezclas      : lista de tuplas (fluid_A, fluid_B)
    water_config : "alta", "media", "alta_7", "media_7", o "media-alta"
                   (este último combina media y alta en el mismo gráfico)
    n_puntos     : puntos de composición entre 0 y 1 (por defecto 41)
    """
    print(f"[graficos_binarios] water_config = {water_config}\n")

    configs = ["media", "alta"] if water_config == "media-alta" else [water_config]

    refs_por_config: dict[str, dict] = {}
    for cfg in configs:
        vhc_min, vhc_max, cop_ref = calcular_valores_referencia(cfg)
        refs_por_config[cfg] = {
            "vhc_min": vhc_min,
            "vhc_max": vhc_max,
            "cop_ref": cop_ref,
            "vhc_ref": (vhc_min + vhc_max) / 2,
        }

    for fluid_a, fluid_b in mezclas:
        graficar_mezcla(fluid_a, fluid_b, water_config, refs_por_config, n_puntos)

    print("\nFinalizado.")


# ---------------------------------------------------------------------------
# Main de ejemplo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_refprop()

    generar_graficos(
        mezclas=[
            ("PROPANE",   "DME"),
            ("PROPYLENE",   "DME"),
            ("CO2",   "DME"),
            ("ETHANE", "DME"),
            ("ETHYLENE",       "DME"),
            ("BUTANE", "DME")
        ],
        water_config="media-alta",   # "alta", "media", "media-alta" (para hacer un gráfico con las dos series)
        n_puntos=41,
    )