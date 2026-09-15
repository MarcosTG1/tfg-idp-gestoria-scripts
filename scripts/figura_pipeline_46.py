#!/usr/bin/env python3
"""Figura del apartado 4.6: recorrido del conjunto de evaluacion por la cadena
de archivo, con los recuentos de cada rama. Cifras de resultados_45.json (que ya
consolida la matriz de confusion del 4.2 y el modelo del 4.5).

Salida: memoria/figs/pipeline-archivo.{pdf,png}
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
R44 = json.loads((ROOT / "docs/notes/aut_2/resultados_44.json").read_text())
R45 = json.loads((ROOT / "docs/notes/aut_2/resultados_45.json").read_text())
OUT = ROOT / "memoria" / "figs" / "pipeline-archivo"

TOTAL = 231
POB_A = 158
POB_B = TOTAL - POB_A
DIRECTO = R45["e2e"]["antes"]                 # 127
AMBIGUOS = R45["n"]                           # 29
RESUELTOS = R44["aciertos"]["r1"]            # 25 (regla del flujo R1, por createdTime real)
A_REVISION = R44["sin_resolver"]["r1"]        # 4 (pares del mismo mes -> revision)
NO_RESUELTOS = AMBIGUOS - RESUELTOS           # 4
MODELO_OK = R45["lr"]["bien"]                 # 27 (modelo; no mejora, solo se cita en el pie)
CARPETA_MAL = POB_A - DIRECTO - AMBIGUOS      # 2
ARCHIVADOS = DIRECTO + RESUELTOS              # 127 + R1
PCT_ARCH = 100 * ARCHIVADOS / POB_A

AZUL = "#2166ac"
AZUL_CLARO = "#dbe6f1"
GRIS = "#eeeeee"
BORDE = "#9aa7b4"


def caja(ax, x, y, w, h, texto, relleno=GRIS, negrita=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.02,rounding_size=0.06",
                                facecolor=relleno, edgecolor=BORDE, linewidth=0.8))
    ax.text(x + w / 2, y + h / 2, texto, ha="center", va="center",
            fontsize=9.5, fontweight="bold" if negrita else "normal")
    return (x, y, w, h)


def flecha(ax, a, b, rad=0.0):
    ax1, ay, aw, ah = a
    bx, by, bw, bh = b
    ax.add_patch(FancyArrowPatch((ax1 + aw, ay + ah / 2), (bx, by + bh / 2),
                                 arrowstyle="-|>", mutation_scale=10,
                                 color=BORDE, linewidth=0.9, shrinkA=1, shrinkB=1,
                                 connectionstyle=f"arc3,rad={rad}"))


def main():
    plt.rcParams.update({"font.family": "STIXGeneral", "mathtext.fontset": "stix",
                         "font.size": 9.5})
    fig, ax = plt.subplots(figsize=(7.1, 3.9))
    ax.set_xlim(0, 21)
    ax.set_ylim(0, 13)
    ax.axis("off")

    b0 = caja(ax, 0.2, 5.4, 3.0, 1.8, f"{TOTAL}\npermisos", relleno=AZUL_CLARO)
    bA = caja(ax, 4.5, 8.0, 3.1, 1.7, f"{POB_A}\npoblación A")
    bB = caja(ax, 4.5, 2.4, 3.1, 1.7, f"{POB_B}\npoblación B")

    bDir = caja(ax, 9.1, 10.2, 4.0, 1.6, f"{DIRECTO} · archivo directo")
    bAmb = caja(ax, 9.1, 7.9, 4.0, 1.6, f"{AMBIGUOS} · matrícula ambigua")
    bCar = caja(ax, 9.1, 5.6, 4.0, 1.6, f"{CARPETA_MAL} · carpeta mal rotulada")
    bLec = caja(ax, 9.1, 2.4, 4.6, 1.7,
                f"{POB_B}/{POB_B} · matrícula leída\n(no se archivan)")

    bMod = caja(ax, 14.4, 7.9, 3.6, 1.6,
                f"{RESUELTOS} al expediente\n{NO_RESUELTOS} a revisión")

    bFin = caja(ax, 18.3, 9.1, 2.6, 1.9,
                f"{ARCHIVADOS}/{POB_A}\narchivados\n({PCT_ARCH:.1f} %)".replace(".", ","),
                relleno=AZUL_CLARO, negrita=True)

    flecha(ax, b0, bA)
    flecha(ax, b0, bB)
    flecha(ax, bA, bDir, rad=-0.15)
    flecha(ax, bA, bAmb)
    flecha(ax, bA, bCar, rad=0.15)
    flecha(ax, bB, bLec)
    flecha(ax, bAmb, bMod)
    flecha(ax, bDir, bFin, rad=-0.1)
    flecha(ax, bMod, bFin, rad=0.1)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(f"{OUT}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("directo", DIRECTO, "ambiguos", AMBIGUOS, "resueltos(R3)", RESUELTOS,
          "carpeta_mal", CARPETA_MAL, "archivados", ARCHIVADOS,
          "| modelo completo llegaria a", DIRECTO + MODELO_OK)
    print("->", OUT.with_suffix(".pdf"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
