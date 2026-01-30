from ctREFPROP.ctREFPROP import REFPROPFunctionLibrary
import re, os, subprocess, json
from typing import Any
from copy import deepcopy

# ERRORES
class ErrorTemperaturaTranscritica(Exception):
    ...

class ErrorPuntoBifasico(Exception):
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

def rprop(fluidos: str | list[str], salida: str | list[str], mezcla: list[float] | None = None, **kwargs: float) -> float | list[float]:
    """
    Función para obtener las propiedades termodinámicas de un fluido a partir de 2 inputs (15% más lento que el DLL)
    
    :param fluidos: En esta variable se declararán los fluidos que se quieran estudiar, tanto separados con ";" o en una lista.
    :type fluidos: str | list[str]
    :param salida: En esta variable se pondrán todas las magnitudes que se quieran del fluido con una string separada por ";"
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
    
    rprop(["CO2", "R290"], "T;H", [0.55, 0.45], P = 5, H = 300)  # Returns [T, H]

    rprop("CO2;R290", ["T", "H"], [0.3, 0.7], P = 5, H = 300)  # Returns [T, H]

    rprop("CO2", "T", [1.0], P = 5, H = 300)  # Returns T (float for single output)
    """

    # Obtener el cliente
    cliente = ClienteRefprop.obtener_instancia()

    # Valor predeterminado de mezcla
    if mezcla is None:
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
    
    # Pasar de bar a MPa en la entrada para presión
    for index, key in enumerate(kwargs.keys()):
        if key.upper() == "P":
            valores_entrada_refprop[index] /= 10

    # Convertir fluidos list[str] -> str con fluid1;fluid2
    if isinstance(fluidos, list):
        fluidos_lista = fluidos
        n_fluidos = len(fluidos)
        if len(fluidos) == 1:
            fluidos_refprop = fluidos[0]
        else:
            fluidos_refprop = ";".join(fluidos)
    elif isinstance(fluidos, str):
        fluidos_lista = fluidos.split(";")
        n_fluidos = len(fluidos_lista)
        fluidos_refprop = fluidos
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
    ncomp = len(fluidos_lista)
    cliente.RP.SETUPdll(ncomp, fluidos_refprop, '', 'DEF')
    res = cliente.RP.REFPROPdll(fluidos_refprop, magnitud_entrada_refprop, salida_refprop, cliente.RP.SI_WITH_C, 1, 0,
                                valores_entrada_refprop[0], valores_entrada_refprop[1], mezcla)
    
    resultados: list[float] = []
    for i in range(len(salida_lista)):
        resultados.append(res.Output[i])

    # Calcular la calidad de vapor si se ha pedido
    if calcular_Q:
        resultados.insert(indice_Q, res.q)

    # Calcular la temperatura y presión crítica aproximada
    if calcular_Pcrit or calcular_Tcrit:
        P_min = 0.5  # MPa
        P_max = 100  # MPa

        P_low = P_min
        P_high = P_max
        eps_P = 0.01

        for _ in range(100):
            P_mid = 0.5 * (P_low + P_high)
            out = cliente.RP.REFPROPdll(fluidos_refprop, "PQ", "P;T", cliente.RP.SI_WITH_C,
                                        1, 0, P_mid, 0.5, mezcla)
            
            if out.ierr != 0:
                P_high = P_mid
                continue
            
            delta_P = abs(P_high - P_low)
            if delta_P > eps_P:
                P_low = P_mid
            else:
                P_crit = P_low
                T_crit = cliente.RP.REFPROPdll(fluidos_refprop, "PQ", "T", cliente.RP.SI_WITH_C,
                                                 1, 0, P_low, 0.5, mezcla).Output[0]
                break
        else:
            raise RuntimeError("Las propiedades críticas no convergen")

    if calcular_Pcrit:
        resultados.insert(indice_Pcrit, P_crit)
    if calcular_Tcrit:
        resultados.insert(indice_Tcrit, T_crit)

    # Pasar de MPa a bar la salida
    for index in indices_presion:
        resultados[index] *= 10

    # Return single value if only one output, else list
    return resultados[0] if len(resultados) == 1 else resultados

class Serializable:
    def to_dict(self):
        raise NotImplemented
    
    @classmethod
    def from_dict(cls, dic):
        raise NotImplemented

class TPoint(Serializable):
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

    def __init__(self, fluido: str | list[str], mezcla: list[float] | None = None, **kwargs) -> None:
        # Guardar el input
        self.fluido = fluido
        self.mezcla = mezcla
        self.kwargs = kwargs
        for clave, valor in kwargs.items():
            setattr(self, clave, valor)

        # Obtener el cliente
        self.cliente = ClienteRefprop.obtener_instancia()
    
    def _compute(self, nombre):
        return rprop(self.fluido, nombre, self.mezcla, **self.kwargs)
    
    def __getattr__(self, nombre):
        """
        Si no se pide un atributo y no se ha calculado previamente se intercepta para calcularlo
        """
        if nombre in self._props:
            valor = self._compute(nombre)
            setattr(self, nombre, valor)
            return valor
        raise AttributeError(f"Atributo {nombre} no existe. Posibles atrubutos: {self._props}")
    
    def calcular(self, *args) -> None:
        """
        Calcular varios valores a la vez y guardarlos en el objeto para
        que si se quieren varios valores no se pidan al dll de 1 en 1.
        """
        salida_lista = []
        for arg in args:
            salida_lista.append(arg)
        resultado = rprop(self.fluido, salida_lista, self.mezcla, **self.kwargs)

        for nombre, valor in zip(args, resultado):
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
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "__class__": self.__class__.__name__,
            "fluido": self.fluido,
            "mezcla": self.mezcla,
            "kwargs": self.kwargs
        }
    
    @classmethod
    def from_dict(cls, dic: dict[str, Any]) -> "TPoint":
        return cls(dic["fluido"], dic.get("mezcla"), **dic.get("kwargs"))

class CicloOutput(Serializable):
    def __init__(self, COP: float | None = None,
                 VCC: float | None = None,
                 fluido: str | None = None,
                 mezcla: list[float] | None = None,
                 temperaturas_agua: dict[str, list[float]] | None = None,
                 puntos: dict[str, TPoint] | None = None,
                 puntos_sat: list[TPoint] | None = None,
                 caudales_mas: list[float] | None = None,
                 caudales_vol: list[float] | None = None,
                 pinch: float | None = None,
                 glide: list[float] | None = None,
                 error: str | None = None):
        
        self.COP = COP
        self.VCC = VCC
        self.fluido = fluido
        self.mezcla = mezcla
        self.temperaturas_agua = temperaturas_agua
        self.puntos = puntos
        self.puntos_sat = puntos_sat
        self.caudales_mas = caudales_mas
        self.caudales_vol = caudales_vol
        self.pinch = pinch
        self.glide = glide
        self.error = error

    def to_dict(self) -> dict[str, Any]:

        return {"__class__": self.__class__.__name__,
                "__data__": serializar(self.__dict__),
        }

    
    @classmethod
    def from_dict(cls, dic: dict[str, Any]) -> "CicloOutput":
        obj = cls.__new__(cls)
        obj.__dict__ = deserializar(dic["__data__"])
        return obj

def serializar(obj):
    if isinstance(obj, Serializable):
        return obj.to_dict()
    
    if isinstance(obj, dict):
        return {k: serializar(v) for k, v in obj.items()}
    
    if isinstance(obj, (list, tuple, set)):
        t = type(obj)
        return t(serializar(v) for v in obj)
    
    return obj

REGISTRO_CLASES = {
    "TPoint": TPoint,
    "CicloOutput": CicloOutput
}

def deserializar(obj):
    if isinstance(obj, dict):
        if "__class__" in obj:
            cls = REGISTRO_CLASES[obj["__class__"]]
            return cls.from_dict(obj)

        return {k: deserializar(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        t = type(obj)
        return t(deserializar(v) for v in obj)

    return obj

def diagrama_PH(fluido: str | list[str], mezcla: list[float], P_min: float, P_max: float, H_min: float,
                H_max: float, num_puntos_sat: int, num_puntos_temp: int, base_log: float,
                play: bool | None = None, puntos: list[TPoint] | None = None) -> None:
    
    # Nombre del script donde se genera la imagen
    script_imagen = "refprop_graph.py"

    # Si se abre o no al acabar de generar la imagen
    if not play:
        comando_calidad = "-qk"
    else:
        comando_calidad = "-pqk"

    # Añadir un título personalizado a la imagen en función del fluido
    if isinstance(fluido, str):
        fluido_lista = fluido.split(";")
    elif isinstance(fluido, list):
        fluido_lista = fluido
    else:
        raise TypeError(f"La variable fluido debe ser de tipo: str | list[str], no de tipo {type(fluido)}")

    titulo_foto = ""
    for fluid, proporcion in zip(fluido_lista, mezcla):
        titulo_foto += fluid + f"_{(proporcion*100):.0f}%"


    comando = ["manim", comando_calidad, script_imagen, "PHDiagram", "-o", titulo_foto]

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

def puntos_PH(puntos: list[TPoint], base_log: float, margen: float | None = 0.2, play: bool | None = None) -> None:
    punto1 = puntos[0]
    fluido = punto1.fluido
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

    num_puntos_sat = 200
    num_puntos_temp = 200

    diagrama_PH(fluido, mezcla, P_min, P_max, H_min, H_max, num_puntos_sat, num_puntos_temp, base_log, play, TPoint_a_lista(puntos))

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

