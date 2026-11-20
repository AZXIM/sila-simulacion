import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import animation, patches
from matplotlib.colors import LinearSegmentedColormap

ANCHO_REJILLA = 4.50
LARGO_SUMERGIDO = 5.12
PASO_BARROTES = 0.040
ANCHO_TOBERA = 0.32
V_CARRO = 0.10
Q = 0.005
H = 6.0
RHO = 1025.0
G = 9.81
ETA_VORTEX = 0.42
CW = 0.06
RPM_BOMBA = 2500
MASA_SESION = 360.0
T_SESION = 20 * 60
HUMEDAD = 0.85
RENDIMIENTO_BIOCHAR = 0.30
SESIONES_DIA_PICO = 3

N_PASADAS = int(round(ANCHO_REJILLA / ANCHO_TOBERA))
T_CARRERA = LARGO_SUMERGIDO / V_CARRO
T_MANIOBRA = (T_SESION - N_PASADAS * T_CARRERA) / (N_PASADAS - 1)
P_HIDRAULICA = RHO * G * Q * H
P_EJE = P_HIDRAULICA / ETA_VORTEX
CAPACIDAD_SESION = Q * T_SESION * RHO * CW

FONDO = "#141414"
PANEL = "#1F1F1C"
AGUA = "#26312F"
LINEA_AGUA = "#8FA9B3"
ALGA = "#B3C52D"
BRASA = "#E0491F"
BLANCO = "#F2F2EC"
GRIS = "#8A8A82"

plt.rcParams.update({
    "font.family": ["Fira Sans", "DejaVu Sans"],
    "text.color": BLANCO,
    "axes.edgecolor": GRIS,
    "axes.labelcolor": GRIS,
    "xtick.color": GRIS,
    "ytick.color": GRIS,
})
TITULO = dict(fontfamily=["Anton", "DejaVu Sans"], fontweight="normal")
cmap_alga = LinearSegmentedColormap.from_list(
    "alga", [(0, 0, 0, 0), (0.70, 0.77, 0.18, 0.55), (0.37, 0.42, 0.08, 0.97)])

FPS = 30
F_INTRO = int(2.5 * FPS)
F_SESION = int(15 * FPS)
F_BIO = int(5.0 * FPS)
F_CIERRE = int(2.5 * FPS)
F_TOTAL = F_INTRO + F_SESION + F_BIO + F_CIERRE

NX, NY = N_PASADAS * 6, 72
rng = np.random.default_rng(7)
ruido = rng.random((NY, NX))
for _ in range(6):
    ruido = (ruido + np.roll(ruido, 1, 0) + np.roll(ruido, -1, 0)
             + np.roll(ruido, 1, 1) + np.roll(ruido, -1, 1)) / 5
ruido = (ruido - ruido.min()) / (ruido.max() - ruido.min())
gradiente = np.linspace(1.0, 0.55, NY)[:, None]
densidad_final = np.clip(0.25 + 0.9 * ruido * gradiente, 0, 1)
kg_por_unidad = MASA_SESION / densidad_final.sum()


def estado_tobera(t):
    ciclo = T_CARRERA + T_MANIOBRA
    pasada = min(int(t // ciclo), N_PASADAS - 1)
    t_local = t - pasada * ciclo
    if t_local <= T_CARRERA:
        return pasada, t_local / T_CARRERA, True
    return pasada, 1.0, False


def campo_en(t):
    d = densidad_final.copy()
    pasada, frac, _ = estado_tobera(t)
    ancho = NX // N_PASADAS
    d[:, : pasada * ancho] *= 0.04
    filas = int(frac * NY)
    if filas > 0:
        d[NY - filas:, pasada * ancho:(pasada + 1) * ancho] *= 0.04
    if t >= T_SESION:
        d[:] = densidad_final * 0.04
    return d


def construir_figura():
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=FONDO)
    fig.text(0.04, 0.915, "S.I.L.A.  ·  GEMELO DIGITAL DE UNA SESIÓN DE LIMPIEZA",
             fontsize=36, color=BLANCO, **TITULO)

    ax = fig.add_axes([0.06, 0.14, 0.48, 0.72], facecolor=AGUA)
    ax.set_xlim(0, ANCHO_REJILLA)
    ax.set_ylim(0, LARGO_SUMERGIDO)
    ax.set_xticks(np.arange(0, ANCHO_REJILLA + 0.01, 0.5))
    ax.set_yticks(np.arange(0, LARGO_SUMERGIDO + 0.01, 1.0))
    ax.set_xlabel("Ancho de rejilla (m)", fontsize=13)
    ax.set_ylabel("Longitud sumergida (m)", fontsize=13)
    for x in np.arange(PASO_BARROTES, ANCHO_REJILLA, PASO_BARROTES):
        ax.axvline(x, color="#C9D6DC", lw=0.6, alpha=0.55, zorder=1)
    img = ax.imshow(densidad_final, extent=(0, ANCHO_REJILLA, 0, LARGO_SUMERGIDO),
                    cmap=cmap_alga, vmin=0, vmax=1, origin="upper", zorder=2,
                    interpolation="bilinear")
    tobera = patches.FancyBboxPatch((0, 0), ANCHO_TOBERA, 0.16, boxstyle="round,pad=0.01",
                                    fc=BRASA, ec=BLANCO, lw=1.5, zorder=4)
    ax.add_patch(tobera)
    manguera, = ax.plot([], [], color=BRASA, lw=3, zorder=3)
    for s in ax.spines.values():
        s.set_color(GRIS)

    ax_kg = fig.add_axes([0.60, 0.50, 0.36, 0.30], facecolor=PANEL)
    ax_kg.set_xlim(0, T_SESION / 60)
    ax_kg.set_ylim(0, MASA_SESION * 1.12)
    ax_kg.set_title("ALGAS EXTRAÍDAS (kg)", loc="left", fontsize=18, color=BLANCO, **TITULO)
    ax_kg.set_xlabel("Tiempo de sesión (min)")
    linea_kg, = ax_kg.plot([], [], color=ALGA, lw=3)
    ax_kg.axhline(CAPACIDAD_SESION, color=BRASA, ls="--", lw=1.4)
    ax_kg.text(0.3, CAPACIDAD_SESION * 1.02,
               f"Capacidad de la bomba en 20 min: {CAPACIDAD_SESION:.0f} kg",
               color=BRASA, fontsize=11)

    ax_cob = fig.add_axes([0.60, 0.13, 0.36, 0.25], facecolor=PANEL)
    ax_cob.set_xlim(0, T_SESION / 60)
    ax_cob.set_ylim(0, 100)
    ax_cob.set_title("COBERTURA DE ALGAS EN LA REJILLA (%)", loc="left", fontsize=18,
                     color=BLANCO, **TITULO)
    ax_cob.set_xlabel("Tiempo de sesión (min)")
    linea_cob, = ax_cob.plot([], [], color=LINEA_AGUA, lw=3)

    lectura = fig.text(0.60, 0.835, "", fontsize=15, color=BLANCO, family="DejaVu Sans Mono")
    cartel = fig.text(0.04, 0.03, "", fontsize=15, color=BRASA)
    fig.text(0.60, 0.03, "Simulación con parámetros de diseño; cobertura inicial supuesta",
             fontsize=11, color=GRIS)

    barra_fondo = patches.Rectangle((0.06, 0.885), 0.48, 0.006, transform=fig.transFigure,
                                    fc="#2A2A27", ec="none")
    barra = patches.Rectangle((0.06, 0.885), 0.0, 0.006, transform=fig.transFigure,
                              fc=ALGA, ec="none")
    fig.patches.extend([barra_fondo, barra])

    capa = fig.add_axes([0, 0, 1, 1], facecolor=FONDO, zorder=10)
    capa.axis("off")
    capa.set_visible(False)

    return dict(fig=fig, img=img, tobera=tobera, manguera=manguera, linea_kg=linea_kg,
                linea_cob=linea_cob, lectura=lectura, cartel=cartel, capa=capa, barra=barra)


def limpiar_capa(capa):
    capa.clear()
    capa.set_xlim(0, 1)
    capa.set_ylim(0, 1)
    capa.axis("off")
    capa.add_patch(patches.Rectangle((0, 0), 1, 1, fc=FONDO, ec="none", zorder=0))


def dibujar_balance(capa, avance):
    limpiar_capa(capa)
    humeda = MASA_SESION
    seca = humeda * (1 - HUMEDAD)
    biochar = seca * RENDIMIENTO_BIOCHAR
    etapas = [("Alga húmeda\n(1 sesión)", humeda, ALGA),
              ("Alga seca\n(85 % humedad)", seca, "#7E8C1E"),
              ("Biochar\n(30 % rendimiento)", biochar, "#050505")]
    capa.text(0.06, 0.86, "DE LA REJILLA AL BIOCHAR", fontsize=46, color=BLANCO, **TITULO)
    capa.text(0.06, 0.80, "Balance de masa de una sesión de temporada alta",
              fontsize=17, color=GRIS)
    base, alto_max = 0.30, 0.40
    for i, (nombre, kg, color) in enumerate(etapas):
        visible = np.clip(avance * 3 - i, 0, 1)
        x = 0.10 + i * 0.30
        alto = alto_max * (kg / humeda) ** 0.5 * visible
        capa.add_patch(patches.FancyBboxPatch((x, base), 0.18, max(alto, 0.001),
                       boxstyle="round,pad=0.006", fc=color, ec=BLANCO, lw=1.2,
                       alpha=0.95 if visible > 0 else 0))
        if visible > 0.3:
            capa.text(x + 0.09, base + alto + 0.03, f"{kg:,.0f} kg", ha="center",
                      fontsize=42, color=BLANCO, **TITULO)
            capa.text(x + 0.09, base - 0.025, nombre, ha="center", va="top",
                      fontsize=17, color=GRIS)
        if i < 2 and visible > 0.9:
            capa.annotate("", xy=(x + 0.27, base + 0.12), xytext=(x + 0.20, base + 0.12),
                          arrowprops=dict(arrowstyle="-|>", lw=3, color=BRASA))
    if avance > 0.85:
        dia = biochar * SESIONES_DIA_PICO
        capa.text(0.06, 0.06, f"Día de temporada alta ({SESIONES_DIA_PICO} sesiones): "
                  f"~{dia:.0f} kg de biochar y 0 minutos del operador dentro del agua",
                  fontsize=19, color=BRASA, fontweight="bold")


def dibujar_cierre(capa, avance):
    limpiar_capa(capa)
    a = min(1.0, avance * 2)
    capa.text(0.5, 0.60, "S.I.L.A.", ha="center", va="center", fontsize=150,
              color=BLANCO, alpha=a, **TITULO)
    capa.text(0.5, 0.36, "NI A MANO, NI A LA BASURA.", ha="center", va="center",
              fontsize=44, color=ALGA, alpha=a, **TITULO)


def actualizar(frame, h, historial):
    if frame < F_INTRO:
        f = (frame + 1) / F_INTRO
        h["img"].set_data(densidad_final * f)
        h["tobera"].set_visible(False)
        h["cartel"].set_text("Entre limpiezas, las algas filamentosas cubren la rejilla")
        h["lectura"].set_text("Bomba: en espera")
        return
    if frame < F_INTRO + F_SESION:
        t = (frame - F_INTRO) / (F_SESION - 1) * T_SESION
        d = campo_en(t)
        h["img"].set_data(d)
        pasada, frac, limpiando = estado_tobera(t)
        x0 = pasada * ANCHO_REJILLA / N_PASADAS
        y0 = frac * (LARGO_SUMERGIDO - 0.16)
        h["tobera"].set_visible(True)
        h["tobera"].set_x(x0)
        h["tobera"].set_y(y0)
        h["manguera"].set_data([x0 + ANCHO_TOBERA / 2] * 2, [y0 + 0.16, LARGO_SUMERGIDO])
        extraido = (densidad_final.sum() - d.sum()) * kg_por_unidad
        historial["t"].append(t / 60)
        historial["kg"].append(extraido)
        historial["cob"].append(d.mean() * 100)
        h["linea_kg"].set_data(historial["t"], historial["kg"])
        h["linea_cob"].set_data(historial["t"], historial["cob"])
        h["barra"].set_width(0.48 * t / T_SESION)
        mm, ss = divmod(int(t), 60)
        estado = "succionando" if limpiando else "reposicionando"
        h["lectura"].set_text(
            f"Bomba vortex  {RPM_BOMBA:,} rpm | Q {Q*1000:.1f} L/s | P_eje {P_EJE:.0f} W\n"
            f"Pasada {pasada + 1:>2}/{N_PASADAS}  ({estado})   Sesión {mm:02d}:{ss:02d}")
        h["cartel"].set_text("Operador en la pasarela: maneja el carro, no entra al agua")
        return
    h["capa"].set_visible(True)
    if frame < F_INTRO + F_SESION + F_BIO:
        avance = (frame - F_INTRO - F_SESION + 1) / F_BIO
        dibujar_balance(h["capa"], min(1.0, avance * 1.25))
        return
    avance = (frame - F_INTRO - F_SESION - F_BIO + 1) / F_CIERRE
    dibujar_cierre(h["capa"], avance)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--poster-only", action="store_true")
    parser.add_argument("--rapido", action="store_true")
    parser.add_argument("--salida", default="SILA_simulacion.mp4")
    parser.add_argument("--poster", default="SILA_simulacion_poster.png")
    args = parser.parse_args()

    h = construir_figura()
    historial = {"t": [], "kg": [], "cob": []}
    cuadro_poster = F_INTRO + int(F_SESION * 0.55)

    if args.poster_only:
        for fr in range(cuadro_poster + 1):
            actualizar(fr, h, historial)
        h["fig"].savefig(args.poster, facecolor=FONDO)
        return

    dpi, paso = (100, 1) if not args.rapido else (67, 2)
    escritor = animation.FFMpegWriter(fps=FPS // paso, bitrate=8000,
                                      extra_args=["-pix_fmt", "yuv420p"])
    with escritor.saving(h["fig"], args.salida, dpi=dpi):
        for fr in range(F_TOTAL):
            actualizar(fr, h, historial)
            if fr % paso == 0:
                escritor.grab_frame()
            if fr == cuadro_poster:
                h["fig"].savefig(args.poster, facecolor=FONDO)


if __name__ == "__main__":
    main()
