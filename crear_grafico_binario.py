import matplotlib.pyplot as plt
import numpy as np
import os
import json
from refprop_utils import *
from pprint import pprint
from ciclo_basico_3_comp import calcular_valores_referencia, filtrar

def generar_graficos_binarios(casos, valor_referencia):
    output_folder = "graficos_binarios"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for caso in casos:
        nombre = caso["nombre"]
        ejes = caso["ejes"]
        datos = caso["valores"]

        # 1. Extraer y ordenar datos
        sorted_keys = sorted(datos.keys())
        x_values = [k[0] for k in sorted_keys]
        
        # 2. Calcular la desviación porcentual respecto a la referencia
        # Formula: ((valor - ref) / ref) * 100
        y_percent = [((datos[k] - valor_referencia) / valor_referencia) * 100 for k in sorted_keys]

        plt.figure(figsize=(10, 6))
        
        # 3. Dibujar puntos SIN unir (scatter)
        plt.scatter(x_values, y_percent, color='b', label=f'Desviación {nombre}')
        
        # 4. Línea de referencia en el 0%
        plt.axhline(y=0, color='r', linestyle='--', label=f'Referencia ({valor_referencia})')

        # 5. Configurar ticks de los ejes
        # Eje X en porcentajes
        plt.xticks([i/10 for i in range(11)], [f'{i*10}%' for i in range(11)])
        
        # Eje Y con sufijo %
        current_values = plt.gca().get_yticks()
        plt.gca().set_yticklabels([f'{int(x)}%' for x in current_values])

        plt.title(f'Desviación porcentual respecto a referencia: {nombre}', fontsize=12)
        plt.xlabel(f'Composición de {ejes[0]}')
        plt.ylabel('Diferencia de COP respecto a referencia (%)')
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.legend()
        plt.xlim(0, 1)

        plt.savefig(os.path.join(output_folder, f"{nombre}.png"))
        plt.close()

def ciclo_basico_filtrado(fichero_json, fichero_json_filtrado):
    with open(fichero_json, "r", encoding="utf-8") as f:
        dic_res = json.load(f)

    dic_res: dict[str, dict[str, list[CicloOutput]]] = deserializar(dic_res)

    temperaturas_agua = list(list(dic_res.values())[0].values())[0][0].temperaturas_agua
    [vcc_min, vcc_max, cop_propano] = calcular_valores_referencia(temperaturas_agua)

    dic_temp: dict[str, dict[str, list[CicloOutput]]] = {}
    for ref_a, sub_dict in dic_res.items():
        for ref_b, lista_res in sub_dict.items():
            dic_temp.setdefault(ref_a, {})[ref_b] = filtrar(lista_res, vcc_min, vcc_max)

    dic_res = serializar(dic_temp)

    with open(fichero_json_filtrado, "w", encoding="utf-8") as f:
        json.dump(dic_res, f, ensure_ascii=False, indent=4)

def crear_casos(fichero_json: str) -> tuple[list[dict[str, Any]], float]:

    with open(fichero_json, "r", encoding="utf-8") as f:
        dic_res = json.load(f)

    dic_res: dict[str, dict[str, list[CicloOutput]]] = deserializar(dic_res)

    posibles_refrigerantes = list(dic_res.keys())

    temperaturas_agua = list(list(dic_res.values())[0].values())[0][0].temperaturas_agua

    [vcc_min, vcc_max, cop_propano] = calcular_valores_referencia(temperaturas_agua)

    casos: list[dict[str, Any]] = []

    for index_a, ref_a in enumerate(posibles_refrigerantes[:-1]):
        for ref_b in posibles_refrigerantes[index_a + 1:]:
            if dic_res.get(ref_a, {}).get(ref_b):
                lista_resultados = dic_res[ref_a][ref_b]
                fluidos = lista_resultados[0].fluido
                ejes = fluidos
                nombre = (", ").join(fluidos)
                valores = {
                    tuple(res.mezcla): res.COP
                    for res in lista_resultados
                }
                casos.append({
                    "nombre": nombre,
                    "ejes": ejes,
                    "valores": valores,
                })

    return (casos, cop_propano)


def main():

    init_refprop()
    fichero_json = r"resultados\res_ciclo_basico.json"
    fichero_json_filtrado = r"resultados\res_ciclo_basico_filtrado.json"

    ciclo_basico_filtrado(fichero_json, fichero_json_filtrado)

    (casos, cop_propano) = crear_casos(fichero_json_filtrado)

    generar_graficos_binarios(casos, cop_propano)

if __name__ == "__main__":
    main()