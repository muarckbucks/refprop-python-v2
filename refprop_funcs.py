from ctREFPROP.ctREFPROP import REFPROPFunctionLibrary
import re


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

    def rprop(self, fluids: str | list[str], salida: str | list[str], mixture: list[float] | None = None, **kwargs: float) -> list[float]:
        """
        Documentació función rprop (15% más lenta que llamar al dll)
        
        :param fluids: En está variable se declararán los fluidos que se quieran estudiar, tanto separados con ";" o en una lista.
        :type fluids: str | list[str]
        :param salida: En esta varibale se pondrán todas las magnitudes que se quieran del fluido con una string separada por ";"
            o por una lista con las diferentes magnitudes.
        :type salida: str | list[str]
        :param mixture: Esta variable será una lista con las proporciones de los diferentes fluidos, tiene como valor
            predeterminado [1.0]
        :type mixture: list[float] | None
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

        Ejemplo de uso: rprop(["CO2", "R290"], "T;H", [0.55, 0.45], P = 5, H = 300)
        """
        # Valor predeterminado
        if mixture == None:
            mixture = [1.0]
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
        fluids_refprop = ""
        if isinstance(fluids, list):
            if len(fluids) == 1:
                fluids_refprop += fluids[0]
            
            else:
                fluids_refprop = ";".join(fluids)
        
        elif isinstance(fluids, str):
            fluids_refprop = fluids
        
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
            salida_lista.remove("Q")

        if len(salida_lista) != 0:
            salida_refprop = ";".join(salida_lista)
        else:
            salida_refprop = "H"

        # Llamar a REFPROP
        res = self.RP.REFPROPdll(fluids_refprop, magnitud_entrada_refprop, salida_refprop, self.RP.SI_WITH_C, 1, 0,
                                 valores_entrada_refprop[0], valores_entrada_refprop[1], mixture)
        
        resultados: list[float] = []
        for i in range(len(salida_lista)):
           resultados.append(res.Output[i])


        # Calcular la calidad de vapor si se ha pedido
        if calcular_Q:
            resultados.insert(indice_Q, res.q)

        # Pasar de MPa a bar la salida
        for index in indices_presion:
            resultados[index] *= 10



        return resultados

class TPoint:
    """
    Documentación para TPoint (20% más lenta que llamar al dll)
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

    def __init__(self, fluid: str | list[str], mixture: list[float] | None = None, **kwargs) -> None:
        # Guardar el input
        self.fluid = fluid
        self.mixture = mixture
        self.kwargs = kwargs

        # Obtener el cliente
        self.cliente = ClienteRefprop.obtener_instancia()
    
    def _compute(self, nombre):
        return self.cliente.rprop(self.fluid, nombre, self.mixture, **self.kwargs)[0]
    
    def __getattr__(self, nombre):
        """
        Si no se pide un atributo y no se ha calculado se intercepta para calcularlo
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
    
        resultado = self.cliente.rprop(self.fluid, salida_lista, self.mixture, **self.kwargs)

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
        
        print(27*"#")
