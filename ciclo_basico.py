from refprop_utils import * 
from typing import Any

Cliente = ClienteRefprop(r"C:\Program Files (x86)\REFPROP\REFPRP64.DLL")

def calcular_ciclo_basico(fluido: str | list[str], mezcla: list[float],
                   temperaturas_agua: dict[str, list[float]]) -> dict[str, Any]:
    
    resultado: dict[str, Any] = {}

    resultado["fluido"] = fluido
    resultado["mezcla"] = mezcla

    [t_hw_in, t_hw_out] = temperaturas_agua["t_hw"]
    [t_cw_in, t_cw_out] = temperaturas_agua["t_cw"]

    ap_k = 5
    ap_0 = 3

    SH = 5
    SUB = 1

    t3 = t_hw_in + ap_k
    T_crit = rprop(fluido, "Tcrit", mezcla, T = 0, H = 0)

    try:
        if t3 > T_crit:
            raise ErrorTemperaturaTranscritica(f"Temperatura transcrítica en el punto de descarga: {t3:.1f}ºC > {T_crit:.1f}ºC")

        PK = rprop(fluido, "P", mezcla, T = t3 + SUB, Q = 0)

        # Punto 3
        P3 = TPoint(fluido, mezcla, T = t3, P = PK)
        P3.calcular("H", "D")


        # Punto 4
        P4 = TPoint(fluido, mezcla, H = P3.H, T = t_cw_out - ap_0)
        P4.calcular("P", "H", "T")
        P0 = P4.P

        # Rendimiento isentrópico
        rend_iso_h = 0.6

        # Punto 1
        t_sat_1 = rprop(fluido, "T", mezcla, P = P0, Q = 1)
        P1 = TPoint(fluido, mezcla, T = t_sat_1 + SH, P = P0)
        P1.calcular("H", "S", "V")

        # Punto 2
        h_2_s = rprop(fluido, "H", mezcla, P = PK, S = P1.S)
        h_2 = P1.H + (h_2_s - P1.H)/rend_iso_h
        P2 = TPoint(fluido, mezcla, P = PK, H = h_2)
        P2.calcular("H", "Q", "D")
        # if P2.Q <= 1:
        #     raise ErrorPuntoBifasico("El punto de descarga cae en la zona bifásica")

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
        P_hw_in = TPoint("WATER", P = 1, T = t_hw_in)
        P_hw_out = TPoint("WATER", P = 1, T = t_hw_out)
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
        P_water_pinch = TPoint("WATER", P = 1, H = h_water_pinch)
        pinch = Pk_vap_sat.T - P_water_pinch.T

        # Glide
        glide_k = Pk_vap_sat.T - Pk_liq_sat.T
        glide_0 = P0_vap_sat.T - P4.T

        puntos = [P1, P2, P3, P4]
        

        string_resultado = f"""COP = {COP:.4f}
VCC = {VCC:.4f} kJ/m^3
Ratio de caudales másicos respecto a refrigerante: Caliente: {ratio_m_GlycolHot_R:.3f}, Frío: {ratio_m_GlycolCold_R:.3f}
Ratio de caudales volumétricos respecto a refrigerante: Caliente: {ratio_v_GlycolHot_R:.3f}, Frío: {ratio_v_GlycolCold_R:.3f}
Pinch = {pinch:.2f}ºC
Temperaturas de condensación: {Pk_vap_sat.T:.1f}ºC y {Pk_liq_sat.T:.1f}ºC: glide = {glide_k:.1f}ºC
Temperaturas de evaporación: {P0_vap_sat.T:.1f}ºC y {P0_liq_sat.T:.1f}ºC: glide = {glide_0:.1f}ºC
"""
        for i, p in enumerate(puntos, start=1):
            string_resultado += f"Punto {i}: P = {p.P:.2f} bar, H = {p.H:.1f} kJ/kg, T = {p.T:.2f} ºC, Q = {p.Q:.3f}\n"
        
        resultados_adicionales = {
            "COP": COP,
            "VCC": VCC,
            "puntos": puntos,
            "puntos saturados": puntos_saturados,
            "presiones": [PK, P0],
            "caudales másicos": [ratio_m_GlycolHot_R, ratio_m_GlycolCold_R],
            "caudales volumétricos": [ratio_v_GlycolHot_R, ratio_v_GlycolCold_R],
            "pinch": pinch,
            "glide": [glide_k, glide_0],
            "string resultado": string_resultado,
            "error": "-"
        }

        resultado = resultado | resultados_adicionales

    except ErrorPuntoBifasico:
        resultado["COP"] = "-"
        resultado["VCC"] = "-"
        resultado["error"] = "Bifásico"

    except ErrorTemperaturaTranscritica:
        resultado["COP"] = "-"
        resultado["VCC"] = "-"
        resultado["error"] = "Transcrítico"

    except RuntimeError:
        resultado["COP"] = "-"
        resultado["VCC"] = "-"
        resultado["error"] = "REFPROP"

    return resultado




