#!/usr/bin/env python3
"""Dibuja la fila de la matriz de confusion del proceso de archivo (apartado 4.2
de la memoria) y la guarda en memoria/figs/confusion-archivo.{pdf,png}.

Todos los permisos de la poblacion A tienen categoria esperada "archivado", asi
que la matriz de confusion tiene una sola fila con datos. Se representa esa fila
como un mapa de calor de 1x5 (estilo sklearn.metrics.ConfusionMatrixDisplay) con
la barra de color en horizontal debajo, para que ocupe el minimo espacio.

Los recuentos se calculan sobre el conjunto congelado (poblacion A) a partir de
data/raw/dataset_eval/prediccion_42.csv, de modo que la figura sigue en
sincronia con las metricas si el pipeline reimplementado cambia.

Uso:  python scripts/figura_confusion_42.py
"""
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.axes_grid1 import make_axes_locatable

BASE = Path(__file__).resolve().parent.parent
PRED = BASE / "data" / "raw" / "dataset_eval" / "prediccion_42.csv"
OUT = BASE / "memoria" / "figs" / "confusion-archivo"

CATS = [
    ("archivado", "Archivado"),
    ("aviso_multiexpediente", "Aviso\nmulti-exp."),
    ("expediente_duplicado", "Exp.\nduplicado"),
    ("expediente_no_encontrado", "Exp. no\nencontrado"),
    ("sin_matricula", "Sin\nmatrícula"),
]
KEYS = [k for k, _ in CATS]
LABELS = [v for _, v in CATS]


def fila():
    filas = list(csv.DictReader(PRED.read_text(encoding="utf-8").splitlines()))
    v = np.zeros(len(KEYS), dtype=int)
    for r in filas:
        if r["poblacion"] != "A":
            continue
        v[KEYS.index(r["categoria_predicha"])] += 1
    return v


def dibujar(v):
    plt.rcParams.update({
        "font.family": "STIXGeneral",
        "mathtext.fontset": "stix",
        "font.size": 10.5,
        "axes.linewidth": 0.6,
    })
    n = len(LABELS)
    total = int(v.sum())
    m = v.reshape(1, n)

    fig, ax = plt.subplots(figsize=(7.0, 2.35))
    im = ax.imshow(m, cmap="Blues", vmin=0, vmax=m.max(), aspect="auto")

    umbral = m.max() / 2.0
    for j in range(n):
        val = int(v[j])
        txt = f"{val}\n({val / total * 100:.1f}\\%)".replace("\\%", "%").replace(".", ",") if val else "0"
        ax.text(j, 0, txt, ha="center", va="center",
                color="white" if v[j] > umbral else ("#222222" if val else "#9fb8d4"),
                fontsize=10.5 if val else 9,
                fontweight="bold" if j == 0 else "normal")

    ax.set_xticks(np.arange(n))
    ax.set_xticklabels(LABELS, fontsize=9.5)
    ax.xaxis.set_label_position("top")
    ax.xaxis.tick_top()
    ax.set_xlabel("Categoría obtenida por el proceso", labelpad=10)
    ax.set_yticks([0])
    ax.set_yticklabels(["Archivado"])
    ax.set_ylabel("Esperada", labelpad=8)
    ax.tick_params(length=0)

    ax.set_xticks(np.arange(-0.5, n, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 1, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.4)
    ax.tick_params(which="minor", length=0)
    for lado in ("top", "right", "bottom", "left"):
        ax.spines[lado].set_visible(False)

    # barra de color en horizontal, justo debajo de la fila
    cax = make_axes_locatable(ax).append_axes("bottom", size="16%", pad=0.32)
    cbar = fig.colorbar(im, cax=cax, orientation="horizontal")
    cbar.ax.invert_xaxis()  # oscuro a la izquierda, como la celda 127 de arriba
    cbar.ax.set_xlabel("permisos", labelpad=4)
    cbar.outline.set_linewidth(0.6)
    cbar.ax.tick_params(length=2, width=0.6)

    fig.subplots_adjust(left=0.13, right=0.98, top=0.72, bottom=0.20)
    for ext in ("pdf", "png"):
        fig.savefig(f"{OUT}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    v = fila()
    for k, val in zip(KEYS, v):
        print(f"{k:26} {int(val)}")
    print("total poblacion A:", int(v.sum()))
    dibujar(v)
    print("->", OUT.with_suffix(".pdf"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
