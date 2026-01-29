import json
from typing import Any
import numpy as np
from refprop_utils import *
from ciclo_basico import calcular_ciclo_basico

fichero_json = r"resultados\resultados_ciclo_basico.json"

with open(fichero_json, "r", encoding="utf-8") as f:
    data: dict[str, dict[str, list[dict[str, Any]]]] = json.load(f)

posibles_refrigerantes = list(data.keys())

# Inicializar diccionario de resultados
resultado_fino: dict[str, dict[str, dict[str, Any]]] = {}
for index_a, ref_a in enumerate(posibles_refrigerantes):
    resultado_fino[ref_a] = {}
    for index_b, ref_b in enumerate(posibles_refrigerantes):
        if index_a != index_b:
            resultado_fino[ref_a][ref_b] = {}

refrigerantes_revisados: set[str] = set()

for index_1, [ref_1, sub_data_1] in enumerate(data.items()):

    refrigerantes_revisados.add(ref_1)

    for ref_2, lista_resultados in sub_data_1.items():
        
        if ref_2 not in refrigerantes_revisados:

            fluido = lista_resultados[0]["fluido"]
            temperaturas_agua = lista_resultados[0]["temperaturas agua"]
            # Guardar 2 resultados con mayor COP
            lista_res_temp = [res for res in lista_resultados if isinstance(res["COP"], float)]
            lista_resultados = sorted(lista_res_temp, key = lambda resultado: resultado["COP"], reverse = True)[:2]

            # Comprobar cuántos resultados dan COP correcto
            if len(lista_resultados) == 2:
                # Si hay 2 elementos coger los que tienen más COP

                [comp_1, comp_2] = [res["mezcla"] for res in lista_resultados]
 

            elif len(lista_resultados) == 1:
                # Si solo hay un elemento ir desde +- 5% composición
                [comp_1, comp_2] = [lista_resultados[0]["mezcla"] - 0.05, lista_resultados[0]["mezcla"] + 0.05]


            else: # len(lista_resultados) == 0
                # Si no hay resultados saltar la mezcla
                continue
        
            # Crear rango de composiciones que vaya desde el segundo mejor COP al primero
            salto = 0.005
            range_comp: list[float] = [min(comp_1[0], comp_2[0]) + x * salto for x in range(int(abs(comp_1[0] - comp_2[0])/salto) + 1)]

            resultados: list[dict, Any] = []

            for comp in range_comp:
                mezcla = [comp, 1 - comp]
                resultado = calcular_ciclo_basico(fluido, mezcla, temperaturas_agua) # BUG calculant el COP hi ha una divisió per 0 ../(PS.H - P1.H)
                resultados.append(resultado)

                string_comp = ""
                if "glide" in resultado:
                    for fluid, comp in zip(resultado["fluido"], resultado["mezcla"]):
                        string_comp += f"{fluid}: {(comp*100):.1f}%, "
                    print(string_comp + f"COP = {resultado["COP"]:.3f}")
                else:
                    for fluid, comp in zip(resultado["fluido"], resultado["mezcla"]):
                        string_comp += f"{fluid}: {(comp*100):.1f}%, "
                    print(string_comp + f"ERROR = {resultado["error"]}")

            # Quedarse con el COP más grande

            resultados = [res for res in resultados if res["error"] == "-"]
            res_mayor_COP = sorted(resultados, key = lambda resultado: resultado["COP"], reverse = True)[0]

            resultado_fino[ref_1][ref_2] |= res_mayor_COP
            resultado_fino[ref_2][ref_1] |= res_mayor_COP

            string_comp = ""
            for fluid, comp in zip(res_mayor_COP["fluido"], res_mayor_COP["mezcla"]):
                string_comp += f"{fluid}: {(comp*100):.1f}%, "
            print("\nProporción con más COP: " + string_comp + f"COP = {res_mayor_COP["COP"]:.3f}\n")


# Guardar resultados en json
claves_permitidas = {"fluido", "mezcla", "presiones", "caudales másicos", "caudales volumétricos", "COP", "VCC", "pinch", "glide", "error", "temperaturas agua"}
def filtrar_resultados(
    resultados: dict[str, dict[str, dict[str, Any]]],
    claves_permitidas: set[str]
) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        k1: {
            k2: {
                kk: vv for kk, vv in d.items()
                if kk in claves_permitidas
            }
            for k2, d in sub.items()
        }
        for k1, sub in resultados.items()
    }

filtrados = filtrar_resultados(resultados, claves_permitidas)

with open(r"resultados\resultados_finos_basico.json", "w", encoding = "utf-8") as f:
    json.dump(filtrados, f, ensure_ascii=False, indent=2)




            

            