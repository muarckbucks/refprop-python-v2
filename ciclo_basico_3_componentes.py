from refprop_utils import *
from refprop_utils import deserializar, init_refprop
from ciclo_basico import calcular_ciclo_basico, worker_calcular
import numpy as np
import json
import concurrent.futures
import os

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
    
def calcular_resultados(posibles_refrigerantes: list[str], temperaturas_agua: dict[str, list[float]], n_prop: int) -> list[CicloOutput]:
    combinaciones_ref = crear_lista_3_ref(posibles_refrigerantes)
    rango_proporciones = crear_props_3_ref(n_prop) # 21 para que los saltos sean del 5%

    resultados: list[CicloOutput] = []
    # Build task list (each task is (fluido, mezcla, temperaturas_agua))
    tasks = [ (comb_ref, prop, temperaturas_agua)
              for comb_ref in combinaciones_ref
              for prop in rango_proporciones ]

    if tasks:
        cpu = os.cpu_count() or 1
        chunksize = max(1, len(tasks) // (cpu * 4))
        with concurrent.futures.ProcessPoolExecutor(initializer=init_refprop) as ex:
            for res_dict in ex.map(worker_calcular, tasks, chunksize=chunksize):
                res = deserializar(res_dict)
                mostrar_resultado(res)
                resultados.append(res)
    
    return resultados

def pasar_a_diccionario(resultados: list[CicloOutput]) -> dict[str, dict[str, dict[str, list[CicloOutput]]]]:

    dic_resultados: dict[str, dict[str, dict[str, list[CicloOutput]]]] = {}

    for res in resultados:

        [ref_a, ref_b, ref_c] = [res.fluido[i] for i in range(3)]

        dic_resultados.setdefault(ref_a, {}).setdefault(ref_b, {}).setdefault(ref_c, []).append(res)
    
    return dic_resultados

def pasar_a_json(dic_resultados: Any, fichero_json: str) -> None:
    with open(fichero_json, "w", encoding="utf-8") as f:
        json.dump(serializar(dic_resultados), f, ensure_ascii=False, indent=2)

# Cálculo fino

def cargar_json(fichero_json: str) -> dict[str, dict[str, dict[str, list[CicloOutput]]]]:
    with open(fichero_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    return deserializar(data)

def filtrar(lista: list[CicloOutput], vcc_min, vcc_max) -> list[CicloOutput]:
    filtros = [
        lambda r: r.error is None,
        lambda r: vcc_min <= r.VCC <= vcc_max,
        lambda r: r.puntos.get("2").T < 130,
        lambda r: r.pinch > 0,
        lambda r: r.glide[0] < 10 and r.glide[1] < 10,
    ]

    for f in filtros:
        if not lista:
            break
        lista = [r for r in lista if f(r)]

    return sorted(lista, key = lambda r: r.COP, reverse=True) # Si no hay ninguno devolverá []

def calcular_valores_referencia(temperaturas_agua: dict[str, list[float]]) -> list[float]:

    # Calcular VCC de referencia
    margen_vcc = 0.3
    vcc_propano = calcular_ciclo_basico("PROPANE", [1.0],
                                        temperaturas_agua).VCC
    vcc_min = (1 - margen_vcc) * vcc_propano
    vcc_max = (1 + margen_vcc) * vcc_propano
    # Calcular COP de propano
    cop_propano = calcular_ciclo_basico("PROPANE", [1.0],
                                        temperaturas_agua).COP
    
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
            # comparten X → ensanchar Y
            x = props[0][0]
            ys = [p[1] for p in props]
            coords = [[x, y + d] for y in ys for d in dy]
            comps.append(coords)

        else:
            # comparten Y → ensanchar X
            y = props[0][1]
            xs = [p[0] for p in props]
            coords = [[x + d, y] for x in xs for d in dx]
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
    salto = 0.005
    new_comps: list[list[list[float]]] = []

    for coords in comps: 
        x_min, x_max, y_min, y_max = coords

        n_x = int(round((x_max - x_min) / salto)) + 1
        n_y = int(round((y_max - y_min) / salto)) + 1

        comp: list[list[float]] = [
            [x_min + i * salto, y_min + j * salto, 1 - (x_min + i * salto) - (y_min + j * salto)]
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
    
def refinar_mezclas(temperaturas_agua: dict[str, list[float]], fichero_json: str) -> list[CicloOutput]:

    [vcc_min, vcc_max, cop_propano] = calcular_valores_referencia(temperaturas_agua)

    dic_resultados = cargar_json(fichero_json)

    mejores_resultados: list[CicloOutput] = []

    for ref_a, sub_data_a in dic_resultados.items():

        for ref_b, sub_data_b in sub_data_a.items():

            for ref_c, resultados in sub_data_b.items():

                resultados: list[CicloOutput] = filtrar(resultados, vcc_min, vcc_max)[:2] # Filtrar resultados y quedarse con los 2 mayores

                if not resultados:
                    continue

                comps = crear_rango_composiciones(resultados)

                resultados_finos = []
                # Parallelize fine sampling over coords
                tasks = [ ([ref_a, ref_b, ref_c], coord, temperaturas_agua) for comp in comps for coord in comp ]
                if tasks:
                    cpu = os.cpu_count() or 1
                    chunksize = max(1, len(tasks) // (cpu * 4))
                    with concurrent.futures.ProcessPoolExecutor(initializer=init_refprop) as ex:
                        for res_dict in ex.map(worker_calcular, tasks, chunksize=chunksize):
                            resultado = deserializar(res_dict)
                            mostrar_resultado(resultado, 1)
                            resultados_finos.append(resultado)

                resultados_validos = filtrar(resultados_finos, vcc_min, vcc_max) # Volver a filtrar los resultados
                if not resultados_validos:
                    continue

                mejor_resultado = resultados_validos[0]

                mostrar_mejor_resultado(mejor_resultado, cop_propano)

                mejores_resultados.append(mejor_resultado)

    return mejores_resultados

def pasar_a_diccionario_fino(resultados: list[CicloOutput]) -> dict[str, dict[str, dict[str, CicloOutput]]]:

    dic_resultados: dict[str, dict[str, dict[str, CicloOutput]]] = {}

    for res in resultados:
        [ref_a, ref_b, ref_c] = [res.fluido[i] for i in range(3)]

        dic_resultados.setdefault(ref_a, {}).setdefault(ref_b, {})

        dic_resultados[ref_a][ref_b][ref_c] = res

    return dic_resultados



def main():
    init_refprop()
    # DATOS BÁSICOS

    fichero_json = r"resultados\resultados_ciclo_basico_3_comp.json"
    fichero_json_fino = r"resultados\resultados_ciclo_basico_3_comp_fino.json"

    t_hw_in = 47
    t_hw_out = 55

    t_cw_in = 0
    t_cw_out = -3

    temperaturas_agua = {
        "t_hw": [t_hw_in, t_hw_out],
        "t_cw": [t_cw_in, t_cw_out]
    }

    posibles_refrigerantes = ["PROPANE", "CO2", "BUTANE", "ISOBUTANE", "PROPYLENE",
                                "PENTANE", "DME", "ETHANE", "HEXANE", "TOLUENE"]
    
    posibles_refrigerantes = ["PROPANE", "CO2", "BUTANE", "ISOBUTANE"]

    n_prop = 21 # 5% de salto entre proporción y proporción

    n_prop = 5

    # Llamar a las funciones

    # CÁLCULO BRUTO
    resultados = calcular_resultados(posibles_refrigerantes, temperaturas_agua, n_prop)

    dic_resultados = pasar_a_diccionario(resultados)

    pasar_a_json(dic_resultados, fichero_json)

    mejore_resultados = refinar_mezclas(temperaturas_agua, fichero_json)

    pasar_a_json(mejore_resultados, fichero_json_fino)


if __name__ == "__main__":
    main()




