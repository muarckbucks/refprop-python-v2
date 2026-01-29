import json
from typing import Any
import numpy as np
from refprop_utils import *
from ciclo_basico import calcular_ciclo_basico

fichero_json = r"resultados\resultados_ciclo_basico.json"

with open(fichero_json, "r", encoding="utf-8") as f:
    data: dict[str, dict[str, list[dict[str, Any]]]] = json.load(f)

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

                # Comprobar si lo más favorable es 0% o 100% (falta por implementar)
                [comp_1, comp_2] = [res["mezcla"] for res in lista_resultados]

                # Crear rango de composiciones que vaya desde el segundo mejor COP al primero
                salto = 0.005
                range_comp: list[float] = [min(comp_1[0], comp_2[0]) + x * salto for x in range(int(abs(comp_1[0] - comp_2[0])/salto) + 1)]

                for comp in range_comp:
                    mezcla = [comp, 1 - comp]
                    resultados = [calcular_ciclo_basico(fluido, mezcla, temperaturas_agua)]



            elif len(lista_resultados) == 1:
                ...
            else: # len(lista_resultados) == 0
                ...

            

            