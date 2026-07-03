# -*- coding: utf-8 -*-
"""
Diagrama de temperaturas de un condensador (refrigerante vs. posición) frente
al agua que recibe el calor.
Requiere que la función `rprop` (basada en REFPROP) esté disponible.
Ajusta el import de abajo según donde tengas definida esa función.
"""
from refprop_utils import rprop, init_refprop   # <-- AJUSTA este import al lugar real de tu función rprop
import matplotlib.pyplot as plt
# =============================================================================
#                       PARÁMETROS MODIFICABLES
# =============================================================================
# --- Refrigerante ---
FLUIDOS = ["PROPANE", "CO2"]      # Lista de fluidos (componentes de la mezcla)
PROPORCIONES = [0.96, 0.04]         # Proporciones molares de cada fluido (misma longitud que FLUIDOS)
P_COND = 25                     # Presión de condensación [bar]
T_INICIO_REFRIGERANTE = 90      # Temperatura de entrada del refrigerante (supercalentado) [ºC]
T_FIN_REFRIGERANTE = 55         # Temperatura de salida del refrigerante (subenfriado) [ºC]
# --- Agua ---
T_INICIO_AGUA = 47              # Temperatura de entrada del agua [ºC]
T_FIN_AGUA = 55                 # Temperatura de salida del agua [ºC]
# --- Discretización y gráfico ---
N_PUNTOS = 100                     # Número de puntos a lo largo del condensador
TITULO_GRAFICO = "Perfil de temperaturas en el condensador"
ETIQUETA_EJE_X = "Posición del condensador"
LEYENDA_REFRIGERANTE = "R290/R744 (96%/4%)"   # Nombre de la serie del refrigerante en la leyenda
LEYENDA_AGUA = "Agua"                   # Nombre de la serie del agua en la leyenda
LEYENDA_PINCH = "Pinch point"           # Nombre de la flecha de pinch en la leyenda
SOMBREAR = True                         # Si es True, sombrea el área entre las dos series
PINCH = True                            # Si es True, dibuja una flecha amarilla <--> en el punto de pinch
# =============================================================================
def calcular_perfil_refrigerante(fluidos, mezcla, p_cond_bar, t_in, t_out, n_puntos):
    """
    Calcula el perfil de temperatura del refrigerante a lo largo del condensador.
    Se asume que la entalpía avanza de forma proporcional a la posición
    (interpolación lineal entre la entalpía de entrada y la de salida a la
    presión de condensación dada), y en cada paso se recalcula la temperatura
    a partir de (P, H).

    El resultado se devuelve ya invertido para representar el flujo en
    contracorriente respecto al agua: la entrada del refrigerante (t_in,
    supercalentado) queda alineada con la salida del agua, y la salida del
    refrigerante (t_out, subenfriado) queda alineada con la entrada del agua.
    """
    # Entalpía de entrada (supercalentado) y salida (subenfriado) a la presión de condensación
    h_in = rprop(fluidos, "H", mezcla, P=p_cond_bar, T=t_in)
    h_out = rprop(fluidos, "H", mezcla, P=p_cond_bar, T=t_out)
    posiciones = [i / (n_puntos - 1) for i in range(n_puntos)]
    temperaturas = []
    for x in posiciones:
        h_x = h_in + (h_out - h_in) * x  # entalpía interpolada linealmente con la posición
        t_x = rprop(fluidos, "T", mezcla, P=p_cond_bar, H=h_x)
        temperaturas.append(t_x)
    # Contracorriente: invertimos el orden de las temperaturas manteniendo las mismas posiciones
    temperaturas = temperaturas[::-1]
    return posiciones, temperaturas
def calcular_perfil_agua(t_in, t_out, n_puntos):
    """
    Calcula el perfil de temperatura del agua a lo largo del condensador,
    asumiendo que la temperatura avanza linealmente con la posición.
    """
    posiciones = [i / (n_puntos - 1) for i in range(n_puntos)]
    temperaturas = [t_in + (t_out - t_in) * x for x in posiciones]
    return posiciones, temperaturas
def interpolar_lineal(x_lista, y_lista, x_objetivo):
    """
    Interpola linealmente el valor de y en x_objetivo a partir de dos listas
    de puntos (x_lista, y_lista) ordenadas de forma creciente en x.
    """
    for i in range(len(x_lista) - 1):
        x0, x1 = x_lista[i], x_lista[i + 1]
        if x0 <= x_objetivo <= x1:
            y0, y1 = y_lista[i], y_lista[i + 1]
            if x1 == x0:
                return y0
            return y0 + (y1 - y0) * (x_objetivo - x0) / (x1 - x0)
    # Si está fuera de rango, se devuelve el extremo más cercano
    return y_lista[0] if x_objetivo < x_lista[0] else y_lista[-1]
def calcular_posicion_pinch(fluidos, mezcla, p_cond_bar, t_in, t_out):
    """
    Calcula la posición (en el eje x, ya en coordenadas de contracorriente)
    en la que el refrigerante empieza a condensar, es decir, el punto en el
    que alcanza la condición de vapor saturado (Q = 1) a la presión de
    condensación dada.
    """
    h_in = rprop(fluidos, "H", mezcla, P=p_cond_bar, T=t_in)
    h_out = rprop(fluidos, "H", mezcla, P=p_cond_bar, T=t_out)
    h_rocio = rprop(fluidos, "H", mezcla, P=p_cond_bar, Q=1.0)  # entalpía de vapor saturado (inicio de condensación)
    x_rocio = (h_rocio - h_in) / (h_out - h_in)  # posición sin invertir (0 = entrada del refrigerante)
    # Se invierte para que coincida con la representación en contracorriente
    x_pinch = 1 - x_rocio
    return x_pinch
def graficar(pos_ref, temp_ref, pos_agua, temp_agua, titulo, etiqueta_x, leyenda_ref, leyenda_agua,
             sombrear, pinch, x_pinch=None, leyenda_pinch="Pinch point"):
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(pos_ref, temp_ref, color="#d62728", linewidth=2.2, label=leyenda_ref)
    ax.plot(pos_agua, temp_agua, color="#1f77b4", linewidth=2.2, label=leyenda_agua)
    if sombrear:
        # Sombrea el área entre las dos curvas (por debajo del refrigerante y por encima del agua)
        ax.fill_between(pos_ref, temp_agua, temp_ref, color="#9b59b6", alpha=0.15)
    if pinch and x_pinch is not None:
        # Flecha vertical <--> amarilla desde el agua hasta el refrigerante en el punto donde empieza a condensar
        y_agua_pinch = interpolar_lineal(pos_agua, temp_agua, x_pinch)
        y_ref_pinch = interpolar_lineal(pos_ref, temp_ref, x_pinch)
        ax.annotate(
            "", xy=(x_pinch, y_ref_pinch), xytext=(x_pinch, y_agua_pinch),
            arrowprops=dict(arrowstyle="<->", color="#f1c40f", linewidth=1.8)
        )
        # Línea "fantasma" (sin datos visibles) únicamente para que aparezca en la leyenda
        ax.plot([], [], color="#f1c40f", linewidth=1.8, label=leyenda_pinch)
    # Eje Y: temperatura, con etiqueta y unidades
    ax.set_ylabel("Temperatura (ºC)")
    # Eje X: posición, con etiqueta pero sin marcas ni unidades, y sin margen extra
    ax.set_xticks([])
    ax.set_xlabel(etiqueta_x)
    ax.set_xlim(min(pos_ref[0], pos_agua[0]), max(pos_ref[-1], pos_agua[-1]))
    ax.set_title(titulo)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig
if __name__ == "__main__":
    init_refprop()
    pos_ref, temp_ref = calcular_perfil_refrigerante(
        FLUIDOS, PROPORCIONES, P_COND, T_INICIO_REFRIGERANTE, T_FIN_REFRIGERANTE, N_PUNTOS
    )
    pos_agua, temp_agua = calcular_perfil_agua(T_INICIO_AGUA, T_FIN_AGUA, N_PUNTOS)
    x_pinch = None
    if PINCH:
        x_pinch = calcular_posicion_pinch(
            FLUIDOS, PROPORCIONES, P_COND, T_INICIO_REFRIGERANTE, T_FIN_REFRIGERANTE
        )
    fig = graficar(
        pos_ref, temp_ref, pos_agua, temp_agua,
        TITULO_GRAFICO, ETIQUETA_EJE_X, LEYENDA_REFRIGERANTE, LEYENDA_AGUA, SOMBREAR,
        PINCH, x_pinch, LEYENDA_PINCH
    )
    fig.savefig("cond_temp_glide.png", dpi=150)