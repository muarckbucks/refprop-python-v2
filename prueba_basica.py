from refprop_funcs import * 
from typing import Any

Cliente = ClienteRefprop(r"C:\Program Files (x86)\REFPROP\REFPRP64.DLL")


def calcular_ciclo(fluido: str | list[str], mezcla: list[float],
                   temperaturas_agua: dict[str, list[float]]) -> dict[str, Any]:
    

    [t_hw_in, t_hw_out] = temperaturas_agua["t_hw"]
    [t_cw_in, t_cw_out] = temperaturas_agua["t_cw"]

    ap_k = 5
    ap_0 = 3

    SH = 5
    SUB = 1

    t3 = t_hw_in + ap_k
    T_crit = rprop(fluido, "Tcrit", mezcla, T = 0, H = 0)[0]


    if t3 > T_crit:
        raise ValueError("Temperatura transcrítica")
    else:
        PK = rprop(fluido, "P", mezcla, T = t3 + SUB, Q = 0)[0]

        # Punto 3
        P3 = TPoint(fluido, mezcla, T = t3, P = PK)


        # Punto 4
        P4 = TPoint(fluido, mezcla, H = P3.H, T = t_cw_out - ap_0)
        P0 = P4.P

        # Rendimiento isentrópico
        rend_iso_h = 1

        # Punto 1
        t_sat_1 = rprop(fluido, "T", mezcla, P = P0, Q = 1)[0]
        P1 = TPoint(fluido, mezcla, T = t_sat_1 + SH, P = P0)

        # Punto 2
        h_2_s = rprop(fluido, "H", mezcla, P = PK, S = P1.S)[0]
        h_2 = P1.H + (h_2_s - P1.H)/rend_iso_h
        P2 = TPoint(fluido, mezcla, P = PK, H = h_2)

        # COP y VCC
        COP = (P2.H - P3.H)/(P2.H - P1.H)
        VCC = (P2.H - P1.H)/P1.V

        # Puntos saturados
        Pk_liq_sat = TPoint(fluido, mezcla, P = PK, Q = 0)
        Pk_vap_sat = TPoint(fluido, mezcla, P = PK, Q = 1)

        P0_liq_sat = TPoint(fluido, mezcla, P = P0, Q = 0)
        P0_vap_sat = TPoint(fluido, mezcla, P = P0, Q = 1)

        puntos_saturados = [Pk_liq_sat, Pk_vap_sat, P0_liq_sat, P0_vap_sat]
        # Caudales
        P_hw_in = TPoint("ETHYLENEGLYCOL", P = 1, T = t_hw_in)
        P_hw_out = TPoint("ETHYLENEGLYCOL", P = 1, T = t_hw_out)
        P_cw_in = TPoint("ETHYLENEGLYCOL", P = 1, T = t_cw_in)
        P_cw_out = TPoint("ETHYLENEGLYCOL", P = 1, T = t_cw_out)

        # Relaciones másicas
        ratio_m_GlycolHot_R = (P2.H - P3.H)/(P_hw_out.H - P_hw_in.H)
        ratio_m_GlycolCold_R = (P1.H - P4.H)/(P_cw_in.H - P_cw_out.H)

        # Relaciones volumétricas
        ratio_v_GlycolHot_R = ratio_m_GlycolHot_R * P2.D/P_hw_in.D
        ratio_v_GlycolCold_R = ratio_m_GlycolCold_R * P3.D/P_cw_in.D

        # Pinch
        h_water_pinch = P_hw_out.H - 1/ratio_m_GlycolHot_R * (P2.H - Pk_vap_sat.H)
        P_water_pinch = TPoint("ETHYLENEGLYCOL", P = 1, H = h_water_pinch)
        pinch = Pk_vap_sat.T - P_water_pinch.T


        puntos = [P1, P2, P3, P4]
        resultado = {
            "COP": COP,
            "VCC": VCC,
            "puntos": puntos,
            "puntos saturados": puntos_saturados,
            "Presiones": [PK, P0],
            "Caudales másicos": [ratio_m_GlycolHot_R, ratio_m_GlycolCold_R],
            "Caudales volumétricos": [ratio_v_GlycolHot_R, ratio_v_GlycolCold_R],
            "Pinch": pinch,
        }

        return resultado

def mostrar_resultados(resultado: dict[str, Any]) -> None:
    # Extraer datos
    puntos: list[TPoint] = resultado["puntos"]
    [P1, P2, P3, P4] = puntos
    puntos_saturados: list[TPoint] = resultado["puntos saturados"]
    [Pk_liq_sat, Pk_vap_sat, P0_liq_sat, P0_vap_sat] = puntos_saturados
    COP = resultado["COP"]
    VCC = resultado["VCC"]
    [PK, P0] = resultado["Presiones"]
    [ratio_m_GlycolHot_R, ratio_m_GlycolCold_R] = resultado["Caudales másicos"]
    [ratio_v_GlycolHot_R, ratio_v_GlycolCold_R] = resultado["Caudales volumétricos"]
    pinch = resultado["Pinch"]

    # Representar resultado
    print(f"COP = {COP:.4f}")
    print(f"VCC = {VCC:.4f} kJ/m^3")

    print(f"Ratio de caudales másicos respecto a refrigerante: Caliente: {ratio_m_GlycolHot_R:.3f}, Frío: {ratio_m_GlycolCold_R:.3f}")
    print(f"Ratio de caudales volumétricos respecto a refrigerante: Caliente: {ratio_v_GlycolHot_R:.3f}, Frío: {ratio_v_GlycolCold_R:.3f}")
    print(f"Pinch = {pinch:.2f}ºC")
    glide_k = Pk_vap_sat.T - Pk_liq_sat.T
    glide_0 = P0_vap_sat.T - P4.T
    print(f"Temperaturas de condensación: {Pk_vap_sat.T:.1f}ºC y {Pk_liq_sat.T:.1f}ºC: glide = {glide_k:.1f}ºC")
    print(f"Temperaturas de evaporación: {P0_vap_sat.T:.1f}ºC y {P0_liq_sat.T:.1f}ºC: glide = {glide_0:.1f}ºC")

    for i, p in enumerate(puntos, start = 1):
        print(f"Punto {i}: P = {p.P:.2f} bar, H = {p.H:.1f} kJ/kg, T = {p.T:.2f} ºC, Q = {p.Q:.3f}")


# Datos iniciales
fluido = "PROPANE"
mezcla = [1.0]

t_hw_in = 47.
t_hw_out = 55.

t_cw_in = 0.
t_cw_out = -3.

temperaturas_agua = {
    "t_hw": [t_hw_in, t_hw_out],
    "t_cw": [t_cw_in, t_cw_out]
}

resultado = calcular_ciclo(fluido, mezcla, temperaturas_agua)

if __name__ == "__main__":
    mostrar_resultados(resultado)
    puntos_PH(resultado["puntos"], base_log = 1.5, margen = 0.2)


