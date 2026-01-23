from refprop_funcs import *

CR = ClienteRefprop(r"C:\Program Files (x86)\REFPROP\REFPRP64.DLL")

fluido = "PROPANE"

T_hw_in = 47
T_hw_out = 55

T_cw_in = 0
T_cw_out = -3

Ap_k = 3
Ap_0 = 1

SH = 5
SUB = 1

P0 = rprop(fluido, "P", T = T_cw_out - Ap_0, Q = 0)[0]
PK = rprop(fluido, "P", T = T_hw_in + Ap_k, Q = 1)[0]

rend_iso_h = 1

# Punto 1
t_sat_1 = rprop(fluido, "T", P = P0, Q = 1)[0]
P1 = TPoint(fluido, P = P0, T = t_sat_1 + SH)
P1.calcular("H;S")

# Punto 2
h_2_s = rprop(fluido, "H", P = PK, S = P1.S)[0]
h_2 = P1.H + (h_2_s - P1.H)/rend_iso_h
P2 = TPoint(fluido, P = PK, H = h_2)

# Punto 3
t_sat_3 = rprop(fluido, "T", Q = 0, P = PK)[0]
P3 = TPoint(fluido, P = PK, T = t_sat_3 - SUB)

# Punto 4
P4 = TPoint(fluido, P = P0, H = P3.H)


# COP
COP = (P2.H - P3.H)/(P2.H - P1.H)
print(f"{COP:.4f}")

puntos = [P1, P2, P3, P4]
for i, p in enumerate(puntos, start = 1):
    print(f"Punto {i}: P = {p.P:.4f} bar, H = {p.H:.4f} kJ/kg, T = {p.T:.4f} ºC, Q = {p.Q:.4f}")
    