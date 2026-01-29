from refprop_utils import *
from ciclo_basico import *
import numpy as np
import json

Cliente = ClienteRefprop(r"C:\Program Files (x86)\REFPROP\REFPRP64.DLL")

def main():
    # DATOS BÁSICOS
    mezcla = [1.0]

    t_hw_in = 47
    t_hw_out = 55

    t_cw_in = 0
    t_cw_out = -3

    temperaturas_agua = {
        "t_hw": [t_hw_in, t_hw_out],
        "t_cw": [t_cw_in, t_cw_out]
    }

    # T_DIS MAX = 130ºc
    # PINCH > 0ºc
    #GLIDE < 10ºC

    posibles_refrigerantes = ["CO2", "BUTANE", "ISOBUTANE", "PROPYLENE",
                              "PENTANE", "DME", "ETHANE", "PROPANE", "HEXANE",
                              "TOLUENE"]

    # posibles_refrigerantes = ["PROPANE", "BUTANE", "DME"]


    
    # Inicializar diccionario de resultados
    resultados: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for index_a, ref_a in enumerate(posibles_refrigerantes):
        resultados[ref_a] = {}
        for index_b, ref_b in enumerate(posibles_refrigerantes):
            if index_a != index_b:
                resultados[ref_a][ref_b] = []

    # Calcular mezclas de refrigerantes
    for index_a, ref_a in enumerate(posibles_refrigerantes[:-1]):

        for index_b, ref_b in enumerate(posibles_refrigerantes[index_a+1:]):

            props_a = list(np.linspace(0, 1, 21))
            props_a = [float(x) for x in props_a]
            
            for prop_a in props_a:
                prop_b = 1 - prop_a
                mezcla = [prop_a, prop_b]


                resultado = calcular_ciclo_basico([ref_a, ref_b], mezcla, temperaturas_agua)
                # Ir imprimiendo resultados
                string_comp = ""

                # Comprobar si no ha dado error el cálculo
                if "glide" in resultado:
                    for fluid, comp in zip(resultado["fluido"], resultado["mezcla"]):
                        string_comp += f"{fluid}: {(comp*100):.0f}%, "
                    print(string_comp + f"COP = {resultado["COP"]:.3f}")
                else:
                    for fluid, comp in zip(resultado["fluido"], resultado["mezcla"]):
                        string_comp += f"{fluid}: {(comp*100):.0f}%, "
                    print(string_comp + f"ERROR = {resultado["error"]}")                    
                # puntos_PH(resultado["puntos"], 1.5, 0.2)

                resultados[ref_a][ref_b].append(resultado)
                resultados[ref_b][ref_a].append(resultado)

        
    # Guardar resultados en json
    claves_permitidas = {"fluido", "mezcla", "presiones", "caudales másicos", "caudales volumétricos", "COP", "VCC", "pinch", "glide", "error", "temperaturas agua"}
    def filtrar_resultados(resultados: dict[str, dict[str, list[dict[str, Any]]]],
                           claves_permitidas = set[str]) -> dict[str, dict[str, list[dict[str, Any]]]]:
        return {
            k1 : {
                k2 : [
                    {kk: vv for kk, vv in d.items() if kk in claves_permitidas}
                    for d in lista
                ]
                for k2, lista in sub.items()

            }
            for k1, sub in resultados.items()
        }

    filtrados = filtrar_resultados(resultados, claves_permitidas)

    with open(r"resultados\resultados_ciclo_basico.json", "w", encoding="utf-8") as f:
        json.dump(filtrados, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
    
