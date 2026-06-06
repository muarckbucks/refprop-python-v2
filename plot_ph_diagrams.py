"""
plot_ph_diagrams.py
-------------------
Genera un diagrama P-H comparativo para múltiples fluidos/mezclas en una
sola figura de matplotlib. No abre la ventana; devuelve el objeto Figure.
 
rprop trabaja en °C y bar.
 
Dependencias: matplotlib, numpy, ciclo_ternario (rprop, calcular_ciclo_basico,
              init_refprop).
"""
 
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.colors import to_rgba
from typing import Optional
 
from ciclo_ternario import rprop, calcular_ciclo_basico, init_refprop
 
matplotlib.use("Agg")  # backend sin pantalla
 
# ---------------------------------------------------------------------------
# Nombres ASHRAE
# ---------------------------------------------------------------------------
 
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

# Presión mínima de saturación [bar] por fluido.
# Por debajo de este umbral la DLL falla (zona sublimación / punto triple).
# El CO2 tiene punto triple en ~5.18 bar; se usa 5.5 bar como margen seguro.
_P_MIN_SAT: dict[str, float] = {
    "CO2": 5.5,
}
 
 
def _ashrae_label(fluid: list[str], comp: list[float]) -> str:
    """
    Genera la etiqueta de leyenda con nombres ASHRAE.
    Formato: 'RE170' para fluido puro,
             'R290/R1270/R600 (0.20/0.30/0.50)' para mezclas.
    Si el fluido no está en ASHRAE_NAMES se usa su nombre original.
    """
    names = [ASHRAE_NAMES.get(f, f) for f in fluid]
    if len(fluid) == 1:
        return names[0]
    name_str = "/".join(names)
    frac_str  = "/".join(f"{round(c*100):g}%" for c in comp)
    return f"{name_str} ({frac_str})"
 
 
# ---------------------------------------------------------------------------
# Helpers REFPROP
# ---------------------------------------------------------------------------
 
def _sat_curve(fluid: list[str], composition: list[float],
               n_points: int = 300,
               p_min_sat: Optional[float] = None) -> tuple[np.ndarray, np.ndarray,
                                                            np.ndarray, np.ndarray]:
    """
    Calcula la curva de saturación (líquido + vapor) del fluido/mezcla.
 
    rprop trabaja en °C y bar.
    Ttriple no funciona en esta DLL (devuelve -9999999), se ignora.
 
    Estrategia para T_min (°C):
      - Barre desde -180 °C hacia Tcrit en pasos finos de 1 °C.
      - La primera T donde rprop acepta (T, Q=0) sin excepción es T_min.
      - Si p_min_sat está definido, se avanza además hasta que la presión
        de saturación supere ese umbral (útil para el CO2, cuyo punto
        triple ronda los 5.18 bar y la DLL falla por debajo).

    Parámetros adicionales
    ----------------------
    p_min_sat : float | None
        Presión mínima [bar] por debajo de la cual no se intentan calcular
        puntos de saturación. None → sin restricción adicional.
 
    Devuelve:
        h_liq, p_liq  – entalpías [kJ/kg] y presiones [bar], rama líquido
        h_vap, p_vap  – entalpías [kJ/kg] y presiones [bar], rama vapor
    """
    T_crit_C = rprop(fluid, "Tcrit", composition, T=0, H=0)
 
    # Barrido descendente para encontrar T_min real del fluido (°C)
    T_min_C = None
    for T_probe in np.arange(-180, T_crit_C - 1, 1.0):
        try:
            rprop(fluid, "H", composition, T=float(T_probe), Q=0)
            T_min_C = float(T_probe)
            break
        except Exception:
            continue
 
    if T_min_C is None:
        raise RuntimeError(
            f"No se encontró T_min para {fluid} entre -180 °C y {T_crit_C:.1f} °C"
        )

    # Parche para fluidos con punto triple notable (ej. CO2 ~5.18 bar):
    # avanzar T_min_C hasta que P_sat supere p_min_sat, evitando que la DLL
    # intente evaluar la bifase en la zona de sublimación.
    if p_min_sat is not None:
        for T_probe in np.arange(T_min_C, T_crit_C - 1, 0.5):
            try:
                p_test = rprop(fluid, "P", composition, T=float(T_probe), Q=0)
                if p_test >= p_min_sat:
                    T_min_C = float(T_probe)
                    break
            except Exception:
                continue
 
    temps = np.linspace(T_min_C, T_crit_C - 0.05, n_points)
 
    h_liq, p_liq, h_vap, p_vap = [], [], [], []
 
    for T in temps:
        try:
            h_l, p_l = rprop(fluid, ["H", "P"], composition, T=float(T), Q=0)
            h_v, p_v = rprop(fluid, ["H", "P"], composition, T=float(T), Q=1)
            h_liq.append(h_l); p_liq.append(p_l)
            h_vap.append(h_v); p_vap.append(p_v)
        except Exception:
            continue
 
    return (np.array(h_liq), np.array(p_liq),
            np.array(h_vap), np.array(p_vap))
 
 
def _draw_cycle(ax, row: dict, color, cycle_alpha: float,
                cycle_linewidth: float, cycle_linestyle: str) -> None:
    """
    Dibuja las líneas del ciclo termodinámico (1→2→3→4→1)
    a partir del dict devuelto por calcular_ciclo_basico.
    Solo líneas, sin marcadores de puntos.
 
    _fila_ok desempaqueta pts en columnas planas: h_1, p_1, h_2, p_2, ...
    """
    if row.get("error") is not None:
        return
 
    try:
        h1, p1 = row["h_1"], row["p_1"]
        h2, p2 = row["h_2"], row["p_2"]
        h3, p3 = row["h_3"], row["p_3"]
        h4, p4 = row["h_4"], row["p_4"]
    except KeyError:
        return
 
    cycle_color = to_rgba(color, alpha=cycle_alpha)
    kw = dict(color=cycle_color, linewidth=cycle_linewidth,
              linestyle=cycle_linestyle, solid_capstyle="round",
              solid_joinstyle="round")
 
    ax.plot([h1, h2], [p1, p2], **kw)   # 1→2 compresión
    ax.plot([h2, h3], [p2, p3], **kw)   # 2→3 condensación
    ax.plot([h3, h4], [p3, p4], **kw)   # 3→4 expansión isoentálpica
    ax.plot([h4, h1], [p4, p1], **kw)   # 4→1 evaporación
 
 
# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------
 
def plot_ph_diagrams(
    fluids: list[list[str]],
    compositions: list[list[float]],
    colors: Optional[list[str]] = None,
    *,
    # ── ciclo ──────────────────────────────────────────────────────────────
    puntos_ciclo: bool = False,
    water_config: str = "default",
    cycle_alpha: float = 0.45,
    cycle_linewidth: float = 1.5,
    cycle_linestyle: str = "-",
    # ── límites manuales del gráfico (None → autoescala) ───────────────────
    h_min: Optional[float] = None,
    h_max: Optional[float] = None,
    p_min: Optional[float] = None,
    p_max: Optional[float] = None,
    # ── opciones de curva de saturación ────────────────────────────────────
    n_points: int = 50,
    linewidth: float = 2.0,
    linestyle: str = "-",
    # ── opciones de figura ──────────────────────────────────────────────────
    figsize: tuple[float, float] = (12, 7),
    dpi: int = 150,
    title: str = "Diagramas P-H comparativos",
    xlabel: str = "Entalpía específica  h  [kJ/kg]",
    ylabel: str = "Presión  P  [bar]",
    log_p: bool = True,
    grid: bool = True,
) -> plt.Figure:
    """
    Dibuja las curvas de saturación de varios fluidos/mezclas en un solo
    diagrama P-H sin abrir ninguna ventana. rprop trabaja en °C y bar.
 
    Parámetros
    ----------
    fluids : list[list[str]]
        Ej: [["DME"], ["PROPANE", "BUTANE"]]
    compositions : list[list[float]]
        Fracciones molares, deben sumar 1. Ej: [[1.0], [0.4, 0.6]]
    colors : list[str] | None
        Colores matplotlib por mezcla. None → paleta tab10.
    puntos_ciclo : bool
        Si True superpone el ciclo 1→2→3→4→1 (semitransparente, mismo color).
    water_config : str
        Pasado a calcular_ciclo_basico.
    cycle_alpha : float
        Opacidad de las líneas del ciclo (0 invisible – 1 sólido).
    cycle_linewidth : float
        Grosor de línea del ciclo.
    cycle_linestyle : str
        Estilo de línea del ciclo.
    h_min, h_max : float | None
        Límites eje X [kJ/kg].
    p_min, p_max : float | None
        Límites eje Y [bar].
    n_points : int
        Resolución de la curva de saturación.
    linewidth : float
        Grosor de la curva de saturación.
    linestyle : str
        Estilo de la curva de saturación.
    figsize, dpi, title, xlabel, ylabel, log_p, grid : varios
        Opciones estándar de figura matplotlib.
 
    Devuelve
    --------
    fig : matplotlib.figure.Figure
        Figura sin mostrar. Úsala con fig.savefig(...) o fig.show().
 
    Ejemplo
    -------
    >>> init_refprop()
    >>> fig = plot_ph_diagrams(
    ...     fluids       = [["DME"], ["PROPANE", "PROPYLENE", "BUTANE"]],
    ...     compositions = [[1.0],   [0.2, 0.3, 0.5]],
    ...     colors       = ["steelblue", "tomato"],
    ...     puntos_ciclo = True,
    ...     water_config = "HT",
    ...     cycle_alpha  = 0.4,
    ...     h_min=100, h_max=700, p_min=0.5, p_max=50,
    ... )
    >>> fig.savefig("ph_diagram.png", bbox_inches="tight")
    """
    if len(fluids) != len(compositions):
        raise ValueError(
            f"'fluids' y 'compositions' deben tener la misma longitud "
            f"({len(fluids)} vs {len(compositions)})."
        )
 
    default_colors = plt.cm.tab10.colors
    if colors is None:
        colors = [default_colors[i % len(default_colors)]
                  for i in range(len(fluids))]
    elif len(colors) < len(fluids):
        extra = [default_colors[i % len(default_colors)]
                 for i in range(len(colors), len(fluids))]
        colors = list(colors) + extra
 
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    legend_handles = []
 
    for fluid, comp, color in zip(fluids, compositions, colors):
 
        # Etiqueta leyenda con nombres ASHRAE
        label = _ashrae_label(fluid, comp)

        # Límite inferior de presión de saturación específico por fluido.
        # Para mezclas se toma el máximo de los límites de sus componentes
        # (criterio conservador).
        p_min_sat = max(
            (_P_MIN_SAT.get(f, 0.0) for f in fluid),
            default=None,
        ) or None
 
        # Curva de saturación
        try:
            h_liq, p_liq, h_vap, p_vap = _sat_curve(
                fluid, comp, n_points=n_points, p_min_sat=p_min_sat
            )
        except Exception as exc:
            print(f"[AVISO] No se pudo calcular la curva para {fluid}: {exc}")
            continue
 
        ax.plot(h_liq, p_liq, color=color, linewidth=linewidth,
                linestyle=linestyle)
        ax.plot(h_vap, p_vap, color=color, linewidth=linewidth,
                linestyle=linestyle)
 
        # Líneas de cierre hacia el punto crítico (sin marcador)
        if len(h_liq) and len(h_vap):
            try:
                T_crit_C = rprop(fluid, "Tcrit", comp, T=0, H=0)
                h_cp, p_cp = rprop(fluid, ["H", "P"], comp,
                                   T=T_crit_C, Q=0)
                # líquido: último punto de la rama → crítico
                ax.plot([h_liq[-1], h_cp], [p_liq[-1], p_cp],
                        color=color, linewidth=linewidth, linestyle=linestyle)
                # vapor: último punto de la rama → crítico
                ax.plot([h_vap[-1], h_cp], [p_vap[-1], p_cp],
                        color=color, linewidth=linewidth, linestyle=linestyle)
            except Exception:
                pass
 
        legend_handles.append(
            Line2D([0], [0], color=color, linewidth=linewidth,
                   linestyle=linestyle, label=label)
        )
 
        # Ciclo termodinámico
        if puntos_ciclo:
            # Rellenamos hasta 3 componentes para la firma de calcular_ciclo_basico
            f_pad = (fluid + ["", ""])[:3]
            c_pad = (comp  + [0.0, 0.0])[:3]
            x_A, x_B = c_pad[0], c_pad[1]
 
            try:
                row = calcular_ciclo_basico(
                    fluid_A=f_pad[0], fluid_B=f_pad[1], fluid_C=f_pad[2],
                    x_A=x_A, x_B=x_B,
                    water_config=water_config,
                )
                _draw_cycle(ax, row, color,
                            cycle_alpha=cycle_alpha,
                            cycle_linewidth=cycle_linewidth,
                            cycle_linestyle=cycle_linestyle)
            except Exception as exc:
                print(f"[AVISO] No se pudo calcular el ciclo para {fluid}: {exc}")
 
    # Escala, límites, decoración
    if log_p:
        ax.set_yscale("log")
        # Sin notación científica, sin decimales en el eje Y
        from matplotlib.ticker import FuncFormatter, LogLocator
        def _fmt_p(x, _):
            # Entero si es número redondo, decimal si no
            return f"{x:g}"
        formatter = FuncFormatter(_fmt_p)
        # Ticks mayores y menores en todas las décadas y subdivisiones
        ax.yaxis.set_major_locator(LogLocator(base=10, numticks=20))
        ax.yaxis.set_minor_locator(LogLocator(base=10, subs="auto", numticks=50))
        ax.yaxis.set_major_formatter(formatter)
        ax.yaxis.set_minor_formatter(formatter)
 
    if h_min is not None or h_max is not None:
        ax.set_xlim(left=h_min, right=h_max)
    if p_min is not None or p_max is not None:
        ax.set_ylim(bottom=p_min, top=p_max)
 
    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold")
 
    if grid:
        ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.6)
 
    if legend_handles:
        ax.legend(handles=legend_handles, loc="upper left", framealpha=0.9,
                  fontsize=10, title="Fluido",
                  title_fontsize=10)
 
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Ejemplo de uso directo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_refprop()

    fluids_list = [
        ["PROPANE"],
        ["DME"],
        ["CO2"],
        ["METHANE"],
        ["ETHANE"],
        ["ETHYLENE"]
    ]
    compositions_list = [
        [1],
        [1],
        [1],
        [1],
        [1],
        [1]
    ]
    my_colors = ["steelblue", "tomato", "seagreen", "black"]

    fig = plot_ph_diagrams(
        fluids=fluids_list,
        compositions=compositions_list,
        colors=my_colors,
        puntos_ciclo=False,
        water_config="media",
        cycle_alpha=0.6,
        cycle_linewidth=1.5,
        h_min=0,
        h_max=800,
        p_min=2,
        p_max=80,
        log_p=True,
        title="Comparativa de diagramas P-H",
        n_points=150,
    )

    fig.savefig("diagramas_PH/fluidos_puros_volatiles.png", bbox_inches="tight")
    print("Figura guardada")