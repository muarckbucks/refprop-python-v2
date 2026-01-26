from refprop_utils import *
from ciclo_basico import *

Cliente = ClienteRefprop(r"C:\Program Files (x86)\REFPROP\REFPRP64.DLL")

def main():
    # DATOS BÁSICOS
    fluido = "PROPANE;CO2"
    mezcla = [0.55, 0.45]

    t_hw_in = 47
    t_hw_out = 55

    t_cw_in = 0
    t_cw_out = -3

    temperaturas_agua = {
        "t_hw": [t_hw_in, t_hw_out],
        "t_cw": [t_cw_in, t_cw_out]
    }

    resultado = calcular_ciclo_basico(fluido, mezcla, temperaturas_agua)
    try:
        resultado = calcular_ciclo_basico() #BUG temperatura crítica demasiado baja
        print(resultado["string resultado"])
    except ErrorTemperaturaTranscritica as e:
        print(e) # Está mal



if __name__ == "__main__":
    main()
