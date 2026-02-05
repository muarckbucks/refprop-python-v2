import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import ternary
from refprop_utils import *
from ciclo_basico_binario import calcular_ciclo_basico, worker_calcular
import numpy as np
import json, os
from concurrent.futures import ProcessPoolExecutor
from pprint import pprint
from tqdm import tqdm

# Cálculo bruto

def crear_lista_3_ref(posibles_refrigerantes: list[str]) -> list[list[str]]:

    lista_refrigerantes: list[list[str]] = []

    for index_a, ref_a in enumerate(posibles_refrigerantes[:-2]):

        for index_b, ref_b in enumerate(posibles_refrigerantes[index_a + 1:-1]):

            for ref_c in posibles_refrigerantes[index_a + index_b + 2:]:

                lista_refrigerantes.append([ref_a, ref_b, ref_c])
    
    return lista_refrigerantes

def crear_props_3_ref(n_prop: int) -> list[list[float]]:
    lista_props = []
    props = [float(x) for x in list(np.linspace(0, 1, n_prop))]
    for index_a, prop_a in enumerate(props):
        if index_a == 0:
            for prop_b in props:
                prop_c = 1 - prop_a - prop_b
                lista_props.append([prop_a, prop_b, prop_c])
        else:
            for prop_b in props[:-index_a]:
                prop_c = 1 - prop_a - prop_b
                lista_props.append([prop_a, prop_b, prop_c])

    return lista_props

def mostrar_resultado(res: CicloOutput, decimales: int | None = 0) -> None:
    string_comp = ""

    # Comprobar si no ha dado error el cálculo
    if res.error is None:
        for fluid, comp in zip(res.fluido, res.mezcla):
            string_comp += f"{fluid}: {(comp*100):.{decimales}f}%, "
        print(string_comp + f"COP = {res.COP:.3f}")
    else:
        for fluid, comp in zip(res.fluido, res.mezcla):
            string_comp += f"{fluid}: {(comp*100):.{decimales}f}%, "
        print(string_comp + f"ERROR = {res.error}")
    
def calcular_resultados(posibles_refrigerantes: list[str], water_config: str, n_prop: int) -> list[CicloOutput]:
    combinaciones_ref = crear_lista_3_ref(posibles_refrigerantes)
    rango_proporciones = crear_props_3_ref(n_prop)

    resultados: list[CicloOutput] = []

    # Crear lista de inputs (cada input es: [fluido, mezcla, water_config])
    lista_inputs: tuple[list[str], list[float], dict[str, list[float]]] = [
        (comb_ref, prop, water_config)
        for comb_ref in combinaciones_ref
        for prop in rango_proporciones
    ]

    if lista_inputs:
        cpu = os.cpu_count() // 2 or 1 # Usar la mitad de núcleos de la CPU
        chunksize = 2 # Está bien para la duración de la función (aprox 1s)

        print("### CÁLCULO BRUTO ###")

        with ProcessPoolExecutor(max_workers=cpu, initializer=init_refprop) as ex:
            resultados = list(tqdm(ex.map(worker_calcular, lista_inputs, chunksize=chunksize), total=len(lista_inputs))) # Devuelve ya serializado
    
    return deserializar(resultados)

def pasar_a_diccionario(resultados: list[CicloOutput]) -> dict[str, dict[str, dict[str, list[CicloOutput]]]]:

    dic_resultados: dict[str, dict[str, dict[str, list[CicloOutput]]]] = {}

    for res in resultados:

        [ref_a, ref_b, ref_c] = [res.fluido[i] for i in range(3)]

        dic_resultados.setdefault(ref_a, {}).setdefault(ref_b, {}).setdefault(ref_c, []).append(res)
    
    return dic_resultados

def pasar_a_json(dic_resultados: Any, water_config: str) -> None:
    fichero_json = "resultados.json"
    path_json = os.path.join("resultados_ciclo_basico", water_config, "ternarias", fichero_json)

    os.makedirs(os.path.dirname(path_json), exist_ok=True)
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(serializar(dic_resultados), f, ensure_ascii=False, indent=2)

def pasar_a_json_filtrado(dic_resultados: Any, water_config: str) -> None:
    fichero_json = "resultados_filtrados.json"
    path_json = os.path.join("resultados_ciclo_basico", water_config, "ternarias", fichero_json)

    os.makedirs(os.path.dirname(path_json), exist_ok=True)
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(serializar(dic_resultados), f, ensure_ascii=False, indent=2)    

def filtrar_diccionario(dic_resultados, water_config: str, posibles_refrigerantes: list[str]):

    [vcc_min, vcc_max, cop_propano] = calcular_valores_referencia(water_config)
    
    for [ref_a, ref_b, ref_c] in crear_lista_3_ref(posibles_refrigerantes):
        dic_resultados[ref_a][ref_b][ref_c] = filtrar(dic_resultados[ref_a][ref_b][ref_c], vcc_min, vcc_max)

    return dic_resultados

# Cálculo fino

def cargar_json(water_config: str) -> dict[str, dict[str, dict[str, list[CicloOutput]]]]:
    fichero_json = "resultados.json"
    path_json = os.path.join("resultados_ciclo_basico", water_config, "ternarias", fichero_json)
    
    with open(path_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    return deserializar(data)

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

def filtrar(resultados: list[CicloOutput], vcc_min, vcc_max) -> list[CicloOutput]:
    filtros = [
        lambda r: r.error is None,
        lambda r: vcc_min <= r.VCC <= vcc_max,
        lambda r: r.puntos.get("2").T < 130,
        lambda r: r.puntos.get("2").P < 25,
        lambda r: r.pinch > 1,
        lambda r: r.glide[0] < 10 and r.glide[1] < 10,
    ]

    for f in filtros:
        if not resultados:
            return []
        resultados = [r for r in resultados if f(r)]

    return sorted(resultados, key = lambda r: r.COP, reverse=True) # Si no hay ninguno devolverá []

def calcular_valores_referencia(water_config: str) -> list[float]:

    # Calcular VCC de referencia
    margen_vcc = 0.3
    vcc_propano = calcular_ciclo_basico("PROPANE", [1.0],
                                        water_config).VCC
    vcc_min = (1 - margen_vcc) * vcc_propano
    vcc_max = (1 + margen_vcc) * vcc_propano
    # Calcular COP de propano
    cop_propano = calcular_ciclo_basico("PROPANE", [1.0],
                                        water_config).COP
    
    return [vcc_min, vcc_max, cop_propano]

def crear_rango_composiciones(resultados: list[CicloOutput]) -> list[list[list[float]]]:
    props: list[list[float]] = [r.mezcla[:2] for r in resultados]
    comps: list[list[list[float]]] = []
    if len(resultados) == 2:

        dx = dy = (-0.05, 0.05)

        cerca_x = abs(props[0][0] - props[1][0]) <= 0.1
        cerca_y = abs(props[0][1] - props[1][1]) <= 0.1

        igual_x = props[0][0] == props[1][0]
        igual_y = props[0][1] == props[1][1]

        if not (cerca_x and cerca_y):
            # lejos → cuadrados por punto
            for x, y in props:
                coords = [[x + a, y + b] for a in dx for b in dy]
                comps.append(coords)

        elif not (igual_x or igual_y):
            # cerca pero distintos → cuadrado grande
            xs = [p[0] for p in props]
            ys = [p[1] for p in props]
            coords = [[x, y] for x in xs for y in ys]
            comps.append(coords)

        elif igual_x:
            # comparten X → ensanchar X y puntos entre Y
            x = props[0][0]
            ys = [p[1] for p in props]
            coords = [[x + d, y] for y in ys for d in dx]
            comps.append(coords)

        else:
            # comparten Y → ensanchar Y y puntos entre X
            y = props[0][1]
            xs = [p[0] for p in props]
            coords = [[x, y + d] for x in xs for d in dy]
            comps.append(coords)

    elif len(resultados) == 1:
        dx = dy = (-0.05, 0.05)
        for x, y in props:
            coords = [[x + a, y + b] for a in dx for b in dy]
            comps.append(coords)
        
    
    # Guardar solo x_min, x_max, y_min, y_max
    comps = [
        [
            min(coords, key = lambda coord: coord[0])[0],
            max(coords, key = lambda coord: coord[0])[0],
            min(coords, key = lambda coord: coord[1])[1],
            max(coords, key = lambda coord: coord[1])[1],
        ]
        for coords in comps
    ]
    
    # Crear rangos
    salto = 0.01
    new_comps: list[list[list[float]]] = []

    for coords in comps: 
        x_min, x_max, y_min, y_max = coords

        n_x = int(round((x_max - x_min) / salto)) + 1
        n_y = int(round((y_max - y_min) / salto)) + 1

        comp: list[list[float]] = [
            [round(x_min + i * salto, 3),
             round(y_min + j * salto, 3),
             round(1 - (x_min + i * salto) - (y_min + j * salto), 3)]
            for i in range(n_x)
            for j in range(n_y)
        ]

        new_comps.append(comp)
    
    comps = new_comps
    
    # Filtrar composiciones erróneas
    comps = [
        [
            [x, y, z]
            for x, y, z in comp
            if 0 <= x <= 1 and 0 <= y <= 1 and 0 <= z <= 1
        ]
        for comp in comps
    ]

    return comps

def mostrar_mejor_resultado(res: CicloOutput, cop_propano: float) -> None:
    string_comp = ""

    for fluid, comp in zip(res.fluido, res.mezcla):
        string_comp += f"{fluid}: {(comp*100):.0f}%, "

    proporcion = (res.COP / cop_propano - 1) * 100
    if proporcion >= 0:
        print("\n" + string_comp + f"COP {proporcion:.2f}% más GRANDE que el propano\n")
    else:
        print("\n" + string_comp + f"COP {-proporcion:.2f}% más PEQUEÑO que el propano\n")
    
def refinar_mezclas(water_config: str) -> list[CicloOutput]:

    [vcc_min, vcc_max, cop_propano] = calcular_valores_referencia(water_config)

    # Cargar fichero con resultados de cálculo bruto
    dic_resultados = cargar_json(water_config)

    # Extraer los refrigerantes en el órden que se han calculado
    posibles_refrigerantes = recorrer_refrigerantes(dic_resultados)

    # Crear la lista de combinaciones de refrigerantes
    lista_refrigerantes = crear_lista_3_ref(posibles_refrigerantes)

    # Crear lista de los resultados en orden
    listas_resultados: list[list[CicloOutput]] = [
        dic_resultados[ref_a][ref_b][ref_c]
        for ref_a, ref_b, ref_c in lista_refrigerantes
    ]

    # Filtrar los resultados que no son válidos
    listas_resultados_filtrados = [
        filtrar(resultados, vcc_min, vcc_max)[:2] for resultados in listas_resultados
    ]

    # Calcular todas las posibles combinaciones
    total_comps = [
        crear_rango_composiciones(resultados)
        for resultados in listas_resultados_filtrados
    ]

    # Juntarlo todo en una única variable con todos los inputs
    lista_inputs = []

    for comb_ref, comps in zip(lista_refrigerantes, total_comps):
        for coords in comps:
            for coord in coords:
                lista_inputs.append((comb_ref, coord, water_config))

    print("\n### CÁLCULO FINO ###")

    cpu = os.cpu_count() // 2 or 1 # Usar la mitad de núcleos de la CPU
    chunksize = 2 # Está bien para la duración de la función (aprox 1s)

    # Ejecutar cálculo paralelo
    with ProcessPoolExecutor(max_workers=cpu, initializer=init_refprop) as ex:
        resultados_finos = list(tqdm(ex.map(worker_calcular, lista_inputs, chunksize=chunksize), total=len(lista_inputs)))


    resultados_finos: list[CicloOutput] = deserializar(resultados_finos)

    # Pasar a diccionario para que se pueda filtrar por refrigerantes
    dic_res_finos = pasar_a_diccionario(resultados_finos)

    mejores_resultados: list[CicloOutput] = []
    for sub_dict_1 in dic_res_finos.values():
        for sub_dict_2 in sub_dict_1.values():
            for resultados in sub_dict_2.values():
                filtrados = filtrar(resultados, vcc_min, vcc_max)
                if filtrados:
                    mejores_resultados.append(filtrados[0])

    mejores_resultados.sort(key = lambda res: res.COP, reverse=True) # Ordenar mejores resultados por COP

    return mejores_resultados

def pasar_a_diccionario_fino(resultados: list[CicloOutput]) -> dict[str, dict[str, dict[str, CicloOutput]]]:

    dic_resultados: dict[str, dict[str, dict[str, CicloOutput]]] = {}

    for res in resultados:
        [ref_a, ref_b, ref_c] = [res.fluido[i] for i in range(3)]

        dic_resultados.setdefault(ref_a, {}).setdefault(ref_b, {})

        dic_resultados[ref_a][ref_b][ref_c] = res

    return dic_resultados

def guardar_txt(water_config: str) -> None:
    fichero_json_fino = "resultados_finos.json"
    path_json_fino = os.path.join("resultados_ciclo_basico", water_config, "ternarias", fichero_json_fino)
    
    fichero_txt = "resultados_finos.txt"
    path_txt = os.path.join("resultados_ciclo_basico", water_config, "ternarias", fichero_txt)

    cop_propano = calcular_valores_referencia(water_config)[2]

    with open(path_json_fino, "r") as f:
        list_res: list[CicloOutput] = deserializar(json.load(f))
    
    string_res: list[str] = []

    for res in list_res:
        string_comp = ""

        for fluid, comp in zip(res.fluido, res.mezcla):
            string_comp += f"{fluid}: {abs((comp*100)):.0f}%, "

        string_comp = string_comp[:-2]
        proporcion = (res.COP / cop_propano - 1) * 100

        if proporcion >= 0:
            string_comp += f"\nCOP {proporcion:.2f}% más GRANDE que el propano\n\n"
        else:
            string_comp += f"\nCOP {-proporcion:.2f}% más PEQUEÑO que el propano\n\n"

        string_res.append(string_comp)

    with open(path_txt, "w",encoding="utf-8") as f:
        f.writelines(string_res)

def pasar_a_json_fino(dic_resultados: Any, water_config: str) -> None:
    fichero_json = "resultados_finos.json"
    path_json = os.path.join("resultados_ciclo_basico", water_config, "ternarias", fichero_json)

    os.makedirs(os.path.dirname(path_json), exist_ok=True)
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(serializar(dic_resultados), f, ensure_ascii=False, indent=2)

# Generar gráficos
def generar_graficos_ternarios(casos, referencia, water_config) -> None:
    # Crear la carpeta si no existe
    carpeta_salida = os.path.join("resultados_ciclo_basico", water_config, "ternarias", "graficos")
    if not os.path.exists(carpeta_salida):
        os.makedirs(carpeta_salida)
        print(f"Carpeta '{carpeta_salida}' creada.")

    for caso in casos:
        nombre: str = caso["nombre"]
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

        tax.ticks(axis='lbr', multiple=0.1, linewidth=1, offset=0.02, tick_formats="%.1f")

        # Ocultar el marco cuadrado exterior de Matplotlib
        tax.get_axes().axis('off')

        # Limpiar el fondo
        tax.clear_matplotlib_ticks()
        
        tax.set_title(f"Sistema: {", ".join(nombre.split("_"))}", pad=30)
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

def obtener_datos(water_config) -> tuple[list[dict[str, Any]], float]:
    
    fichero_json = "resultados_filtrados.json"
    path_json_filtrado = os.path.join("resultados_ciclo_basico", water_config, "ternarias", fichero_json)
    
    with open(path_json_filtrado, "r", encoding="utf-8") as f:
        dic_datos = json.load(f)

    dic_datos: dict[str, dict[str, dict[str, list[CicloOutput]]]] = deserializar(dic_datos)

    water_config = list(list(list(dic_datos.values())[0].values())[0].values())[0][0].water_config

    cop_propano = calcular_ciclo_basico("PROPANE", [1.0], water_config).COP

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
    
    # DATOS
    water_config = "media"

    posibles_refrigerantes = ["PROPANE", "BUTANE", "ISOBUTANE", "PROPYLENE", "DME"]
    posibles_refrigerantes = ["PROPANE", "BUTANE", "DME"]
    n_prop = 21 # 5% de salto entre proporción y proporción

    # CÁLCULO BRUTO
    resultados = calcular_resultados(posibles_refrigerantes, water_config, n_prop)

    dic_resultados = pasar_a_diccionario(resultados)

    pasar_a_json(dic_resultados, water_config)

    dic_filtrado = filtrar_diccionario(dic_resultados, water_config,
                                                posibles_refrigerantes)
    
    pasar_a_json_filtrado(dic_filtrado, water_config)

    # CÁLCULO FINO
    mejores_resultados = refinar_mezclas(water_config)

    pasar_a_json_fino(mejores_resultados, water_config)

    guardar_txt(water_config)

    # CREAR GRÁFICOS TERNARIOS
    (datos_casos, cop_propano) = obtener_datos(water_config)

    generar_graficos_ternarios(datos_casos, cop_propano, water_config)


if __name__ == "__main__":
    main()




