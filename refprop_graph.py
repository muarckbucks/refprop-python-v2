from refprop_utils import *
from manim import *
import numpy as np
import os, subprocess, sys, json




# INICIALIZAR CLIENTE
Cliente = ClienteRefprop(r"C:\Program Files (x86)\REFPROP\REFPRP64.DLL")

# DATOS
# Cargar datos (de la función diagrama_PH)
datos = json.loads(os.getenv("DATOS", "{}"))
fluido = datos["fluido"]

mezcla = datos["mezcla"]

P_min = datos["P_min"]
P_max = datos["P_max"]

H_min = datos["H_min"]
H_max = datos["H_max"]

num_puntos_sat = datos["num_puntos_sat"]
num_puntos_temp = datos["num_puntos_temp"]

base_log = datos["base_log"]

# Se pasan los puntos termodinámicos en formato lista porque json no acepta la variable TPoint
puntos_lista: list[list[float]] = datos["puntos"]

# Si no se han pasado puntos se calculará el gráfico sin puntos
if puntos_lista == None:
    calcular_puntos = False
else:
    calcular_puntos = True
    TPoints: list[TPoint] = []
    for punto in puntos_lista:
        # Crear los puntos termodinámicos a partir de la lista
        TPoints.append(TPoint(fluido, mezcla, H = punto[0], P = punto[1]))


# Ajustar H_min y H_max para que sean mútliplos de 50
H_min = int(H_min/50)*50
H_max = np.ceil(H_max/50)*50


# PARÁMETROS ESCALA LOGARÍTMICA
def parametros_log() -> list[float]:
    if base_log != 1:
        coef_log = 1/P_min
        factor_r = H_max/(np.sqrt(2)*np.log(coef_log*P_max)/np.log(base_log)) # Factor que hace que la gráfica tenga ratio 1:sqrt(2)
    else:
        coef_log = 1
        factor_r = 1
        
    config_log = [factor_r, base_log, coef_log]
    return config_log

# FUNCIÓN PARA CONVERTIR A LOGARITMO
def log_trans_list(Presion: list[float], config_log: list[float]) -> list[float]:
    [factor_r, base_log, coef_log] = config_log

    if base_log != 1:
        P_log = [float(factor_r * np.log(p * coef_log)/np.log(base_log)) for p in Presion]
    else:
        P_log = [factor_r * p for p in Presion]

    return P_log
def log_trans_float(Presion: float, config_log: list[float]) -> float:
    [factor_r, base_log, coef_log] = config_log
    
    if base_log != 1:
        P_log = float(factor_r * np.log(Presion * coef_log)/np.log(base_log))
    else:
        P_log = factor_r * Presion

    return P_log

# FUNCIÓN PARA REVERTIR LOGARITMO
def exp_trans_list(Presion: list[float], config_log: list[float]) -> list[float]:
    [factor_r, base_log, coef_log] = config_log

    if base_log != 1:
        P_norm = [float(base_log**(p/factor_r)/coef_log) for p in Presion]
    else:
        P_norm = [p/factor_r for p in Presion]

    return P_norm
def exp_trans_float(Presion: float, config_log: list[float]) -> float:
    [factor_r, base_log, coef_log] = config_log

    if base_log != 1:
        P_norm = float(base_log**(Presion/factor_r)/coef_log)
    else:
        P_norm = Presion/factor_r
        
    return P_norm

# FUNCIÓN PARA CREAR PUNTOS LOGARÍTMICOS EQUIDISTANTES
def log_space(P_min: float, P_max: float, num: int, config_log: list[float]) -> list[list[float]]:
    P_trans = [float(x) for x in np.linspace(log_trans_float(P_min, config_log), log_trans_float(P_max, config_log), num = num)]
    P_normal = list(exp_trans_list(P_trans, config_log))
    return [P_normal, P_trans]

# CÁLCULO DE PARÁMETROS
def parametros_basicos(fluido: str | list[str], mezcla: list[float], config_log: list[float]) -> list[float]:
    # Presiones máximas logarítmicas
    [P_max_trans, P_min_trans] = log_trans_list([P_max, P_min], config_log)

    # Propiedades críticas
    [T_crit, P_crit] = rprop(fluido, "Tcrit;Pcrit", mezcla, P = 0, H = 0)
    H_crit = rprop(fluido, "H", mezcla, P = P_crit, T = T_crit)[0]

    #Temperaturas mínimas y máximas
    T_min = min(rprop(fluido, "T", mezcla, P = P_min, H = H_min)[0], rprop(fluido, "T", mezcla, P = P_max, H = H_min)[0])
    T_max = rprop(fluido, "T", mezcla, P = P_max, H = H_max)[0]
    return [P_max_trans, P_min_trans, T_crit, P_crit, H_crit, T_min, T_max]

# CURVAS DE TEMPERATURA CONSTANTE
def generar_curvas_temperatura(fluido: str | list[str], mezcla: list[float], T_min: float, T_max: float,
                    T_crit: float, num_puntos_temp: int, config_log: list[float] 
                    ) -> list[dict[int, list[list[float]]]]:
    
    # Crear lista de temperaturas 
    lista_temperaturas = list(map(lambda x: x*10, list(range(int(np.ceil(T_min/10)), int(T_max/10)+1))))
    curvas_temperatura_liq: dict[int, list[list[float]]] = {}
    curvas_temperatura_bif: dict[int, list[list[float]]] = {}
    curvas_temperatura_vap: dict[int, list[list[float]]] = {}
    curvas_temperatura_tcrit: dict[int, list[list[float]]] = {}
    # Guardar lista de coordenadas con H y P para cada temeratura
    for temperatura in lista_temperaturas:
        # Si el punto pasa por la campana:
        if temperatura < T_crit:
            Punto_liq_sat = TPoint(fluido, mezcla, Q = 0, T = temperatura)
            Punto_vap_sat = TPoint(fluido, mezcla, Q = 1, T = temperatura)

            # Parte líquida
            curvas_temperatura_liq[temperatura] = [[],[]] # Primero H (x) y luego P (y)
            [presiones, presiones_trans] = log_space(P_max, Punto_liq_sat.P*1.001, num_puntos_temp, config_log)
            curvas_temperatura_liq[temperatura][1] = presiones_trans
            curvas_temperatura_liq[temperatura][0] = [rprop(fluido, "H", mezcla, P = presion, T = temperatura)[0] for presion in presiones]

            # Parte bifásica
            curvas_temperatura_bif[temperatura] = [[],[]]
            entalpias = [float(x) for x in np.linspace(Punto_liq_sat.H, Punto_vap_sat.H, num = num_puntos_temp)]
            curvas_temperatura_bif[temperatura][0] = entalpias
            presiones = [rprop(fluido, "P", mezcla, H = entalpia, T = temperatura)[0] for entalpia in entalpias]
            presiones_trans: list[float] = log_trans_list(presiones, config_log)
            curvas_temperatura_bif[temperatura][1] = presiones_trans
            
            # Parte vapor
            curvas_temperatura_vap[temperatura] = [[],[]]
            [presiones, presiones_trans] = log_space(Punto_vap_sat.P*0.999, P_min, num_puntos_temp, config_log)
            curvas_temperatura_vap[temperatura][1] = presiones_trans
            curvas_temperatura_vap[temperatura][0] = [rprop(fluido, "H", mezcla, P = presion, T = temperatura)[0] for presion in presiones]
        
        # Si el punto pasa por encima de la campana:
        else:
            curvas_temperatura_tcrit[temperatura] = [[],[]]
            [presiones, presiones_trans] = log_space(P_min, P_max, num_puntos_temp, config_log)
            curvas_temperatura_tcrit[temperatura][1] = presiones_trans
            curvas_temperatura_tcrit[temperatura][0] = [rprop(fluido, "H", mezcla, P = presion, T = temperatura)[0] for presion in presiones]
    
    return [curvas_temperatura_liq, curvas_temperatura_bif, curvas_temperatura_vap, curvas_temperatura_tcrit]

# CURVAS PUNTOS SATURADOS
def generar_curvas_saturadas(fluido: str | list[str], mezcla: list[float], config_log: list[float], 
                    P_crit: float, num_puntos_sat: int) -> list[list[list[float]]]:
    
    # Presiones puntos saturados
    [P_sat, P_sat_trans] = log_space(P_min, min(P_max, P_crit), num_puntos_sat, config_log)

    # Entalpias saturadas
    H_liq_sat: list[float] = []
    H_vap_sat: list[float] = []
    for p in P_sat:
        H_liq_sat.append(rprop(fluido, "H", mezcla, Q = 0, P = p)[0])
        H_vap_sat.append(rprop(fluido, "H", mezcla, Q = 1, P = p)[0])
    
    return [[H_liq_sat, P_sat_trans], [H_vap_sat, P_sat_trans]]

# CALCULAR
config_log = parametros_log()

[P_max_trans, P_min_trans, T_crit, P_crit, H_crit, T_min, T_max] = parametros_basicos(fluido, mezcla, config_log)

curvas_temperatura = generar_curvas_temperatura(
    fluido, mezcla, T_min, T_max, T_crit, num_puntos_temp, config_log)

curvas_saturadas = generar_curvas_saturadas(fluido, mezcla, config_log, P_crit, num_puntos_sat)
[[H_liq_sat, P_sat_trans], [H_vap_sat, P_sat_trans]] = curvas_saturadas


# Añadir puntos
if calcular_puntos:
    # Guardarse la coordenada de los puntos
    coord_puntos = [[],[]]
    for punto in TPoints:
        coord_puntos[0].append(punto.H)
        coord_puntos[1].append(log_trans_float(punto.P, config_log))
        

class PHDiagram(Scene):
    def construct(self) -> None:
        
        # Cambiar fondo a blanco
        self.camera.background_color = WHITE #type: ignore

        # Ejes

        ejes = Axes(x_range = [H_min, H_max, 10],
                    y_range = [P_min_trans, P_max_trans, 1],
                    tips = False,
                    
                    x_axis_config = {
                        "numbers_to_include": [x*50 for x in range(int(H_min/50), int(H_max/50)+1)],
                        "decimal_number_config": {
                            "num_decimal_places": 0,
                            "color": BLACK},
                        "font_size": 20,
                        "color": BLACK,
                        "numbers_with_elongated_ticks": [x*50 for x in range(int(H_min/50), int(H_max/50)+1)]
                    },

                    y_axis_config = {
                        "include_numbers": False,
                        "include_ticks": False,
                        "color": BLACK
                    }
                    )

        self.add(ejes)

        x_max = ejes.c2p(H_max, 0)[0]
        x_min = ejes.c2p(H_min, 0)[0]
        y_max = ejes.c2p(0, P_max_trans)[1]
        y_min = ejes.c2p(0, P_min_trans)[1]


        # Marcas de presión personalizadas
        def crear_ticks():
            ticks = VGroup()
            lista_ticks = []
            posibles_ticks = [1, 2, 3, 5, 10] # Números que apareceran en eje y (debe empezar por 1 y acabar por 10)

            def magnitud(P: float) -> int:
                res = np.log10(P)
                if res < 0:
                    res = int(res) - 1
                else:
                    res = int(res)
                return res
            
            magnitud_max = magnitud(P_max)
            magnitud_min = magnitud(P_min)
            
            for index, tick in enumerate(posibles_ticks):
                if P_min <= tick*10**magnitud_min:
                    index_min = index
                    break
            for index, tick in enumerate(posibles_ticks[::-1]):
                if P_max >= tick*10**magnitud_max:
                    index_max = len(posibles_ticks) - index - 1
                    break

            for i in range(magnitud_min, magnitud_max + 1):
                for j in range(len(posibles_ticks) - 1):
                    if i == magnitud_min and j < index_min:
                        continue
                    elif i == magnitud_max and j > index_max:
                        continue
                    else:
                        if i >= 0:
                            n_decimales = 0
                        else:
                            n_decimales = -i
                        lista_ticks.append(round(posibles_ticks[j]*10**i,n_decimales))

            lista_ticks_trans = log_trans_list(lista_ticks, config_log)

            # Añadir los ticks del eje y y el texto correspondiente
            for y, num in zip(lista_ticks_trans, lista_ticks):
                pos = ejes.c2p(H_min, y)
                tick = Line(pos + RIGHT*0.1, pos + LEFT*0.1, color = BLACK, stroke_width = 2)
                self.add(tick)
                texto = Tex(str(num))
                texto.set_color(BLACK)
                texto.scale(0.4)
                texto.move_to(pos + LEFT*0.3)
                self.add(texto)

        crear_ticks()
        # Función que determina si un punto está fuera o dentro de la gráfica
        def en_rango(coords: list[float]) -> bool:
            x = coords[0]
            y = coords[1]
            return (x_min <= x <= x_max) and (y_min <= y <= y_max)

        # Función que crea variables tipo list[Dot] a partir de coordenadas 
        def crear_puntos(H: list[float], P_trans: list[float], radio: float | None = 0.05, color: ManimColor | None = BLACK) -> list[Dot]:
            return [Dot(ejes.c2p(h, p), radius = radio, color = color) for p, h in zip(P_trans, H) if en_rango(ejes.c2p(h, p))]

        # Función que une diferentes puntos (no une el último con el primero)
        def unir_puntos(puntos: list[Dot], color: ManimColor, stroke_width: float | None = None, stroke_opacity: float | None = None) -> list[Line]:
            lineas = []
            kwargs = {"color": color}
            if stroke_width is not None:
                kwargs["stroke_width"] = stroke_width
            if stroke_opacity is not None:
                kwargs["stroke_opacity"] = stroke_opacity
            for d1, d2 in zip(puntos[:-1], puntos[1:]):
                lineas.append(Line(d1.get_center(), d2.get_center(), **kwargs))
            return lineas  

        # Función que une diferentes puntos (sí une el último con el primero)
        def crear_lineas_unidas(puntos: list[Dot], color: ManimColor, stroke_width: float | None = None, stroke_opacity: float | None = None) -> list[Line]:
            lineas: list[Line] = []
            n = len(puntos)
            
            for index in range(n):
                # El operador % n hace que cuando i sea el último, se una con el índice 0
                p_inicio = puntos[index].get_center()
                p_fin = puntos[(index + 1) % n]
                
                linea = Line(p_inicio, p_fin, color=color, stroke_width = stroke_width, stroke_opacity = stroke_opacity)
                lineas.append(linea)
                
            return lineas

        # CREAR RECTÁNGULO DE ENCUADRE
        encuadre = Polygon([x_min, y_min, 0], [x_min, y_max, 0], [x_max, y_max, 0], [x_max, y_min, 0], color = BLACK, stroke_width = 1, stroke_opacity = 0.5)
        self.add(encuadre)

        # LÍNEAS SATURADAS
        # Primero crear puntos
        puntos_liq_sat = crear_puntos(H_liq_sat, P_sat_trans)
        puntos_vap_sat = crear_puntos(H_vap_sat, P_sat_trans)

        # Luego unir los puntos
        lineas_liq_sat = unir_puntos(puntos_liq_sat, color = BLACK)
        lineas_vap_sat = unir_puntos(puntos_vap_sat, color = BLACK)

        lineas_sat = VGroup(lineas_liq_sat, lineas_vap_sat)

        # Añadir las líneas
        self.add(*lineas_sat)

        # LÍNEAS DE TEMPERATURA CONSTANTE
        # Primero crear puntos
        puntos_temperatura: list[dict[int, list[Dot]]] = []
        for index_i, curva in enumerate(curvas_temperatura):
            puntos_temperatura.append({})
            for temperatura, coords in curva.items():
                puntos_temperatura[index_i][temperatura] = crear_puntos(coords[0], coords[1])

                # Añadir texto (temperatura)ºC en la zona bifásica
                if index_i == 1 and temperatura < T_crit:
                    # Hacer la media de coordenadas con Q = 0 y Q = 1 para obtener el centro
                    coord_x = (coords[0][0] + coords[0][-1])/2
                    coord_y = (coords[1][0] + coords[1][-1])/2
                    pos = ejes.c2p(coord_x, coord_y) + UP * 0.15
                    
                    if en_rango(pos):
                        texto = MathTex(f"{temperatura}^\\circ\\text{{C}}")
                        texto.set_color(RED)
                        texto.scale(0.4)
                        texto.move_to(pos)
                        self.add(texto)

                    
        # Luego unir los puntos
        lineas_temperatura: list[dict[int, list[Line]]] = []
        for index, muchos_puntos in enumerate(puntos_temperatura):
            lineas_temperatura.append({})
            for temperatura, puntos in muchos_puntos.items():
                lineas_temperatura[index][temperatura] = unir_puntos(puntos, color = RED, stroke_width = 1.5)

        # Añadir las líneas
        [self.add(*lineas) for muchas_lineas in lineas_temperatura for lineas in muchas_lineas.values()]


        # Añadir puntos termodinámicos si se han dado
        if calcular_puntos:
            puntos_termodinamicos = crear_puntos(coord_puntos[0], coord_puntos[1], radio = 0.08, color = BLUE)
        
            ciclo = crear_lineas_unidas(puntos_termodinamicos, color = BLUE, stroke_width = 5, stroke_opacity = 0.9)
            # Ahora de momento solo se puede hacer un único bucle cerrado, es posible que se tenga que actualizar

            self.add(*puntos_termodinamicos)
            self.add(*ciclo)

