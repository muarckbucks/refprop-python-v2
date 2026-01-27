import json
from typing import Any

fichero_json = r"resultados\resultados_ciclo_basico.json"

with open(fichero_json, "r", encoding="utf-8") as f:
    data: dict[str, dict[str, list[dict[str, Any]]]] = json.load(f)

refrigerantes_revisados: set[str] = set()

for index_1, [ref_1, sub_data_1] in enumerate(data.items()):

    refrigerantes_revisados.add(ref_1)

    for ref_2, lista_resultados in sub_data_1.items():
        
        if ref_2 not in refrigerantes_revisados:

            # Guardar lista ordenada de diccionarios resultado por COP de mayor a menor
            lista_res_temp = [res for res in lista_resultados if isinstance(res["COP"], float)]

            lista_resultados = sorted(lista_res_temp, key = lambda resultado: resultado["COP"], reverse = True)

            


            

            