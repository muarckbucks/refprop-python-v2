from ctREFPROP.ctREFPROP import REFPROPFunctionLibrary
import re, os, subprocess, json

# ERRORES
class ErrorTemperaturaTranscritica(Exception):
    ...

class ClienteRefprop:
    _instancia = None

    def __init__(self, ruta_dll: str):
        self.ruta = ruta_dll
        self.RP = REFPROPFunctionLibrary(ruta_dll)
        ClienteRefprop._instancia = self
    
    @staticmethod
    def obtener_instancia():
        if ClienteRefprop._instancia is None:
            raise RuntimeError("ClienteRefprop no inicializado")
        return ClienteRefprop._instancia

def rprop(fluidos: str | list[str], salida: str | list[str], mezcla: list[float] | None = None, **kwargs: float) -> list[float]:
    """
    Función para obtener las propiedades termodinámicas de un fludio a partir de 2 inputs (15% más lento que el DLL)
    
    :param fluidos: En está variable se declararán los fluidos que se quieran estudiar, tanto separados con ";" o en una lista.
    :type fluidos: str | list[str]
    :param salida: En esta varibale se pondrán todas las magnitudes que se quieran del fluido con una string separada por ";"
        o por una lista con las diferentes magnitudes.
    :type salida: str | list[str]
    :param mezcla: Esta variable será una lista con las proporciones de los diferentes fluidos, tiene como valor
        predeterminado [1.0]
    :type mezcla: list[float] | None
    :param kwargs: Esta variable será un diccionario que contenga los valores de entrada que queramos, por ejemplo:
        (P = 30, H = 480) -> kwargs = {
            "P": 30,
            "H": 480
            }

    Cabe destacar que las unidades son las siguientes:
        Entalpía: kJ/kg
        Presión: bar
        Temperatura: ºC
        Densidad: kg/m^3
        Entropía: kJ/(kg*K)
        Velocidad: m/s
        Viscosidad cinemática: cm^2/s
        Viscosidad dinámica uPa*s
        Conductividad térmica: mW/(m*K)
        Tensión superficial: mN/m
        Masa molar: g/mol

    Ejemplos de uso:
    
    rprop(["CO2", "R290"], "T;H", [0.55, 0.45], P = 5, H = 300)

    rprop("CO2;R290", ["T", "H"], [0.3, 0.7], P = 5, H = 300)

    """

    # Obtener el cliente
    cliente = ClienteRefprop.obtener_instancia()

    # Valor predeterminado de mezcla
    if mezcla == None:
        mezcla = [1.0]
    # Comprobar que solo hay dos entradas en kwargs
    if len(kwargs.keys()) != 2:
        raise ValueError("REFPROP solo admite dos entradas independientes (ej: T y P, T y H…).")
    
    # Convertir kwargs -> str y list[float] mayúsculas
    valores_permitidos = ["T", "P", "D", "E", "H", "S", "Q"]
    magnitud_entrada_refprop: str = ""
    valores_entrada_refprop: list[float] = []
    for clave, valor in kwargs.items():
        clave = clave.upper()
        if clave not in valores_permitidos:
            raise ValueError(f"Propiedad de entrada no permitida: {clave}")
        magnitud_entrada_refprop += clave
        valores_entrada_refprop.append(valor)
    
    # Pasar de MPa a bar en la entrada
    for index, key in enumerate(kwargs.keys()):
        if key == "P":
            valores_entrada_refprop[index] /= 10

    # Convertir fluidos list[str] -> str con fluid1;fluid2
    fluidos_refprop = ""
    if isinstance(fluidos, list):
        n_fluidos = len(fluidos)
        if len(fluidos) == 1:
            fluidos_refprop += fluidos[0]
            fluidos_lista = fluidos
        
        else:
            fluidos_refprop = ";".join(fluidos)
    
    elif isinstance(fluidos, str):
        fluidos_refprop = fluidos
        fluidos_lista = re.findall(r"[;^][^;]+[$;]", fluidos)
        n_fluidos = fluidos_refprop.count(";") + 1
    
    
    else:
        raise TypeError("Tipo incorrecto de fluido, tiene que ser: str o list[str]")

    # Convertir salida str | list[str] -> list[str] mayúsculas
    if isinstance(salida, list):
        salida_lista = [x.upper() for x in salida]
    elif isinstance(salida, str):
        salida_lista: list[str] = re.findall(r"[^;]{1,}", salida.upper())        
    else:
        raise TypeError("Tipo incorrecto de salida, tiene que ser: str o list[str]")
    
    # Guardar índices de presión para después transformar la salida
    indices_presion: list[int] = []
    texto_presion = {"P", "PCRIT"}
    for index, texto in enumerate(salida_lista):
        if texto in texto_presion:
            indices_presion.append(index)


    # Ver si título de vapor está en la lista
    calcular_Q: bool = "Q" in salida_lista
    if calcular_Q:
        indice_Q = salida_lista.index("Q")


    # Ver si Tcrit / Pcrit está en la lista ya que si hay más de
    # 2 fluidos y se piden, refprop no dará una solución correcta

    if "TCRIT" in salida_lista and n_fluidos > 1:
        calcular_Tcrit = True
        indice_Tcrit = salida_lista.index("TCRIT")
    else:
        calcular_Tcrit = False

    if "PCRIT" in salida_lista and n_fluidos > 1:
        calcular_Pcrit = True
        indice_Pcrit = salida_lista.index("PCRIT")
    else:
        calcular_Pcrit = False

    if calcular_Q:
        salida_lista.remove("Q")
    if calcular_Pcrit:
        salida_lista.remove("PCRIT")
    if calcular_Tcrit:
        salida_lista.remove("TCRIT")

    # Pasar la salida de list[str] -> str
    if len(salida_lista) != 0:
        salida_refprop = ";".join(salida_lista)
    else:
        salida_refprop = "H"

    # Llamar a REFPROP
    res = cliente.RP.REFPROPdll(fluidos_refprop, magnitud_entrada_refprop, salida_refprop, cliente.RP.SI_WITH_C, 1, 0,
                                valores_entrada_refprop[0], valores_entrada_refprop[1], mezcla)
    
    resultados: list[float] = []
    for i in range(len(salida_lista)):
        resultados.append(res.Output[i])


    # Calcular la calidad de vapor si se ha pedido
    if calcular_Q:
        resultados.insert(indice_Q, res.q)

    # Calcualr la temperatura y presión crítica aproximada
    if calcular_Pcrit or calcular_Tcrit:
        P_min = 0.5 # MPa
        P_max = 100 # MPa

        P_low = P_min
        P_high = P_max
        P_mid = None
        eps_P = 1e-2

        for _ in range(100):
            P_mid = 0.5 * (P_low + P_high)
            out = cliente.RP.REFPROPdll(fluidos_refprop, "PQ", "P;T", cliente.RP.SI_WITH_C,
                                        1, 0, P_mid, 0, mezcla)
            if out.ierr != 0:
                P_high = P_mid
                continue
            
            delta_P = P_high - P_low
            if delta_P > eps_P:
                P_low = P_mid
            else:
                break

        [P_crit, T_crit] = out.Output[0:2]
        

    if calcular_Pcrit:
        resultados.insert(indice_Pcrit, P_crit)
    if calcular_Tcrit:
        resultados.insert(indice_Tcrit, T_crit)

    # Pasar de MPa a bar la salida
    for index in indices_presion:
        resultados[index] *= 10

    return resultados

class TPoint:
    """
    Clase que guarda un punto termodinámico y calcula sus propiedades a demanda (20% más lento que el DLL)
    """
    # Crear variables para que en el IDE aparezca bonito
    T: float
    P: float
    D: float
    V: float
    E: float
    H: float
    S: float
    Q: float

    # Lista interna de todas las posibles peticiones
    _props = ["T", "P", "D", "V", "E", "H", "S", "Q"]

    def __init__(self, fluid: str | list[str], mezcla: list[float] | None = None, **kwargs) -> None:
        # Guardar el input
        self.fluid = fluid
        self.mezcla = mezcla
        self.kwargs = kwargs
        for clave, valor in kwargs.items():
            setattr(self, clave, valor)

        # Obtener el cliente
        self.cliente = ClienteRefprop.obtener_instancia()
    
    def _compute(self, nombre):
        return rprop(self.fluid, nombre, self.mezcla, **self.kwargs)[0]
    
    def __getattr__(self, nombre):
        """
        Si no se pide un atributo y no se ha calculado previamente se intercepta para calcularlo
        """
        if nombre in self._props:
            valor = self._compute(nombre)
            setattr(self, nombre, valor)
            return valor
        raise AttributeError(f"Atributo {nombre} no existe. Posibles atrubutos: {self._props}")
    
    def calcular(self, salida: str | list[str]) -> None:
        """
        Calcular varios valores a la vez y guardarlos en el objeto para
        que si se quieren varios valores no se pidan al dll de 1 en 1.
        """
        if isinstance(salida, list):
            salida_lista = [x.upper() for x in salida]
        elif isinstance(salida, str):
            salida_lista: list[str] = re.findall(r"[^;]{1,}", salida.upper())        
        else:
            raise TypeError("Tipo incorrecto de salida, tiene que ser: str o list[str]")
    
        resultado = rprop(self.fluid, salida_lista, self.mezcla, **self.kwargs)

        for nombre, valor in zip(salida_lista, resultado):
            setattr(self, nombre, valor)
    
    def mostrar_atributos(self) -> None:
        """
        Muestra los atributos que estan calculados, puede resultar útil cuando no se sabe
        si un atributo se ha calculado y agrupar el cálculo.
        """
        print(8*"#" + " Atributos " + 8*"#")
        for nombre, valor in self.__dict__.items():     
            print(f"{nombre}: {valor}")        
        print(27*"#"+"\n")

def diagrama_PH(fluido: str | list[str], mezcla: list[float], P_min: float, P_max: float, H_min: float,
                H_max: float, num_puntos_sat: int, num_puntos_temp: int, base_log: float, puntos: list[TPoint] | None = None) -> None:
    
    script_animacion = "refprop_graph.py"
    comando = ["manim", "-pqk", script_animacion, "PHDiagram"]

    datos = {
        "fluido": fluido,
        "mezcla": mezcla,
        "puntos": puntos,
        "P_min": P_min,
        "P_max": P_max,
        "H_min": H_min,
        "H_max": H_max,
        "num_puntos_sat": num_puntos_sat,
        "num_puntos_temp": num_puntos_temp,
        "base_log": base_log
    }

    env_vars = {
        **os.environ,
        "DATOS": json.dumps(datos)
    }

    try:
        subprocess.run(comando, check = True, env = env_vars)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")

def TPoint_a_lista(puntos: list[TPoint]) -> list[list[float]]:
    lista: list[dict[str, float]] = []
    [lista.append([punto.H, punto.P]) for punto in puntos]
    return lista

def puntos_PH(puntos: list[TPoint], base_log: float, margen: float | None = 0.2) -> None:
    punto1 = puntos[0]
    fluido = punto1.fluid
    mezcla = punto1.mezcla
    [H_min_punto, H_max_punto, P_min_punto, P_max_punto] = [punto1.H, punto1.H, punto1.P, punto1.P]

    for punto in puntos[1:]:
        if punto.H > H_max_punto:
            H_max_punto = punto.H
        elif punto.H < H_min_punto:
            H_min_punto = punto.H
        if punto.P > P_max_punto:
            P_max_punto = punto.P
        elif punto.P < P_min_punto:
            P_min_punto = punto.P

    H_max = H_max_punto + (H_max_punto - H_min_punto) * margen
    H_min = H_min_punto - (H_max_punto - H_min_punto) * margen
    ratio = P_max_punto / P_min_punto
    factor = ratio ** margen
    P_max = P_max_punto * factor
    P_min = P_min_punto / factor

    num_puntos_sat = 500
    num_puntos_temp = 500

    diagrama_PH(fluido, mezcla, P_min, P_max, H_min, H_max, num_puntos_sat, num_puntos_temp, base_log, TPoint_a_lista(puntos))

def main():

    fluid = "PROPANE"
    mezcla = [1.0]
    P1 = TPoint(fluid, mezcla, P = 2, H = 600)
    P2 = TPoint(fluid, mezcla, P = 15, H = 700)
    P3 = TPoint(fluid, mezcla, P = 15, H = 300)
    P4 = TPoint(fluid, mezcla, P = 2, H = 300)
    puntos = [P1, P2, P3, P4]

    puntos_PH(puntos, base_log = 1.5, margen = 0.2)

if __name__ == "__main__":
    main()

