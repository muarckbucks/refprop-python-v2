import matplotlib.pyplot as plt
import ternary
import os
import json
from typing import Any
from refprop_utils import *
from ciclo_basico_3_comp import *

def generar_graficos_ternarios(casos, referencia, carpeta_salida="graficos_ternarios"):
    # Crear la carpeta si no existe
    if not os.path.exists(carpeta_salida):
        os.makedirs(carpeta_salida)
        print(f"Carpeta '{carpeta_salida}' creada.")

    for caso in casos:
        nombre = caso["nombre"]
        ejes = caso["ejes"]
        valores = caso["valores"]

        v_min = min(valores.values())
        v_max = max(valores.values())

        # Configuración del gráfico
        fig, tax = ternary.figure(scale=1.0)
        fig.set_size_inches(10, 8)

        # Dibujar líneas de la cuadrícula y etiquetas
        tax.boundary(linewidth=2.0)
        tax.gridlines(color="black", multiple=0.1)
        
        tax.set_title(f"Sistema: {nombre}", pad=30)
        tax.left_axis_label(ejes[2], offset=0.14)
        tax.right_axis_label(ejes[1], offset=0.14)
        tax.bottom_axis_label(ejes[0], offset=0.06)

        # Graficar los puntos con lógica de color
        for coords, val in valores.items():
            # Convertir a tupla si viene como lista para evitar errores
            c_tupla = tuple(coords)
            
            # Lógica de color: Rojo si es mayor a ref, Azul si es menor
            color = 'red' if val > referencia else 'blue'
            # Ajustar opacidad según la distancia a la referencia para dar profundidad
            alpha = min(abs(val - referencia) * 2 + 0.3, 1.0) 

            tax.scatter([c_tupla], marker='o', color=color, alpha=alpha, s=100)

        # Limpiar ticks y guardar
        tax.ticks(axis='lbr', linewidth=1, multiple=0.1, tick_formats="%.1f")
        tax.clear_matplotlib_ticks()
        
        path_archivo = os.path.join(carpeta_salida, f"{nombre}.png")
        tax.savefig(path_archivo)
        plt.close()
        print(f"Guardado: {path_archivo}")

def recorrer_refrigerantes(dic: dict[str, any], vistos=None) -> list[str]:
    if vistos is None:
        vistos = set()
    resultado = []
    
    for k, v in dic.items():
        if k not in vistos:
            resultado.append(k)
            vistos.add(k)
        if isinstance(v, dict):
            resultado.extend(recorrer_refrigerantes(v, vistos))
    
    return resultado

def obtener_datos(fichero_json: str) -> tuple[list[dict[str, Any]], float]:
    with open(fichero_json, "r", encoding="utf-8") as f:
        dic_datos = json.load(f)

    dic_datos: dict[str, dict[str, dict[str, list[CicloOutput]]]] = deserializar(dic_datos)

    temperaturas_agua = list(list(list(dic_datos.values())[0].values())[0].values())[0][0].temperaturas_agua

    cop_propano = calcular_ciclo_basico("PROPANE", [1.0], temperaturas_agua).COP

    posibles_refrigerantes = recorrer_refrigerantes(dic_datos)

    lista_refrigerantes = crear_lista_3_ref(posibles_refrigerantes)

    datos_caso: list[dict[str, Any]] = []

    for comb_ref in lista_refrigerantes:

        [ref_a, ref_b, ref_c] = comb_ref

        if dic_datos.get(ref_a, {}).get(ref_b, {}).get(ref_c):

            nombre = "_".join(comb_ref)
            ejes = comb_ref
            valores = {
                tuple(res.mezcla): res.COP
                for res in dic_datos[ref_a][ref_b][ref_c]
            }

        datos_caso.append({
            "nombre": nombre,
            "ejes": ejes,
            "valores": valores,
        })

    return (datos_caso, cop_propano)

def main():
    init_refprop()
    fichero_json = r"resultados\res_ciclo_basico_3_comp_filtrado.json"

    (datos_casos, cop_propano) = obtener_datos(fichero_json)

    generar_graficos_ternarios(datos_casos, cop_propano)

if __name__ == "__main__":
    main()