import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
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

        # Valores mínimo y máximo
        vals = list(valores.values())
        v_min, v_max = min(vals), max(vals)

        # Configuración del gráfico
        fig, tax = ternary.figure(scale=1.0)
        fig.set_size_inches(10, 8)

        # Calculamos cuánto es lo máximo que nos alejamos de la referencia (por arriba o por abajo)
        delta_max = max(abs(v_max - referencia), abs(v_min - referencia))

        # Si delta es 0 (todos los valores son iguales a la ref), ponemos un mínimo para que no de error
        if delta_max == 0: delta_max = 0.001

        # Forzamos los límites simétricos
        sim_vmin = referencia - delta_max
        sim_vmax = referencia + delta_max

        norm = mcolors.TwoSlopeNorm(vmin=sim_vmin, vcenter=referencia, vmax=sim_vmax)

        cmap = plt.get_cmap("coolwarm")

        # Dibujar líneas de la cuadrícula y etiquetas
        tax.boundary(linewidth=2.0)
        tax.gridlines(color="black", multiple=0.1)
        
        tax.set_title(f"Sistema: {nombre}", pad=30)
        tax.left_axis_label(ejes[2], offset=0.14)
        tax.right_axis_label(ejes[1], offset=0.14)
        tax.bottom_axis_label(ejes[0], offset=0.06)

        # Graficar los puntos con lógica de color
        for coords, val in valores.items():
            color_punto = cmap(norm(val))
            tax.scatter([tuple(coords)], marker='o', color=color_punto, 
                        s=150, edgecolors='black', linewidths=0.5, zorder=5)


        # Colorbar
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])

        # Creamos la colorbar
        cb = fig.colorbar(sm, ax=tax.get_axes(), fraction=0.046, pad=0.08)

        # Generamos 5 puntos: [mínimo, intermedio_bajo, referencia, intermedio_alto, máximo]
        ticks_deseados = np.linspace(sim_vmin, sim_vmax, 9)
        cb.set_ticks(ticks_deseados)

        # Generamos las etiquetas dinámicamente
        etiquetas = []
        for t in ticks_deseados:
            if abs(t - referencia) < 1e-7:
                etiquetas.append(f"{referencia:.3f} (Ref)")
            else:
                variacion = ((t / referencia) - 1) * 100
                signo = "+" if variacion > 0 else ""
                etiquetas.append(f"{signo}{variacion:.2f}%")

        cb.set_ticklabels(etiquetas)
        cb.set_label('Variación respecto a Referencia (COP)')
        
        # Guardar foto
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