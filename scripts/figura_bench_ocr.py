#!/usr/bin/env python3
"""Figura del apartado 4.3: exactitud de la lectura de matricula por motor de
OCR, global y en el formato mas dificil (provincial). Lee
docs/notes/aut_2/resultados_43.json (lo genera scripts/metricas_43.py) y guarda
memoria/figs/bench-ocr.{pdf,png}.

Uso:  python scripts/figura_bench_ocr.py
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATOS = ROOT / "docs" / "notes" / "aut_2" / "resultados_43.json"
OUT = ROOT / "memoria" / "figs" / "bench-ocr"

NOMBRE = {"mistral": "Mistral OCR", "paddleocr": "PaddleOCR",
          "doctr": "docTR", "tesseract": "Tesseract"}
ORDEN = ["mistral", "paddleocr", "doctr", "tesseract"]


def main():
    d = json.loads(DATOS.read_text())
    motores = [m for m in ORDEN if m in d["motores"]]

    glob = []
    prov = []
    for m in motores:
        e = d["datos"][m]["estructura"]
        glob.append(e["exactitud"])
        ok, tot = e["por_formato"].get("provincial", [0, 0])
        prov.append(100 * ok / tot if tot else 0)

    plt.rcParams.update({
        "font.family": "STIXGeneral", "mathtext.fontset": "stix",
        "font.size": 10.5, "axes.linewidth": 0.6,
    })
    x = np.arange(len(motores))
    w = 0.38
    fig, ax = plt.subplots(figsize=(6.6, 3.7))
    b1 = ax.bar(x - w / 2, glob, w, label="Todos los formatos",
                color="#2166ac", edgecolor="white", linewidth=0.5)
    b2 = ax.bar(x + w / 2, prov, w, label="Solo matrícula provincial",
                color="#92c5de", edgecolor="white", linewidth=0.5)
    for bars in (b1, b2):
        for r in bars:
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 1.5,
                    f"{r.get_height():.0f}", ha="center", va="bottom", fontsize=9.5)

    ax.set_xticks(x)
    ax.set_xticklabels([NOMBRE[m] for m in motores])
    ax.set_ylabel("Exactitud de matrícula (%)")
    ax.set_ylim(0, 108)
    ax.set_yticks(range(0, 101, 20))
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12),
              ncol=2, fontsize=9.5, handlelength=1.4, columnspacing=1.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(length=0)
    ax.grid(axis="y", color="#dddddd", linewidth=0.6)
    ax.set_axisbelow(True)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(f"{OUT}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("global :", {m: round(g, 1) for m, g in zip(motores, glob)})
    print("prov   :", {m: round(p, 1) for m, p in zip(motores, prov)})
    print("->", OUT.with_suffix(".pdf"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
