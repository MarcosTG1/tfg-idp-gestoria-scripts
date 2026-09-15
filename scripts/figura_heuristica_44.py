#!/usr/bin/env python3
"""Figura del apartado 4.4: para cada regla de asignacion (R1, R2, R3), cuantos
de los 29 permisos ambiguos quedan bien asignados, sin resolver o mal asignados.
Barras horizontales apiladas. Lee docs/notes/aut_2/resultados_44.json.

Uso:  python scripts/figura_heuristica_44.py
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DATOS = ROOT / "docs" / "notes" / "aut_2" / "resultados_44.json"
OUT = ROOT / "memoria" / "figs" / "heuristica-asignacion"

ETIQ = {"r1": "R1", "r2": "R2", "r3": "R3"}


def main():
    d = json.loads(DATOS.read_text())
    n = d["n"]
    reglas = ["r3", "r2", "r1"]  # de abajo a arriba -> R1 arriba

    plt.rcParams.update({
        "font.family": "STIXGeneral", "mathtext.fontset": "stix",
        "font.size": 10.5, "axes.linewidth": 0.6,
    })
    fig, ax = plt.subplots(figsize=(6.7, 2.3))
    y = range(len(reglas))
    cols = {"ok": "#2166ac", "nr": "#c9d7e6", "err": "#e8a0a0"}
    for k, r in enumerate(reglas):
        ok = d["aciertos"][r]
        nr = d["sin_resolver"][r]
        err = n - ok - nr
        x0 = 0
        for val, c, lab in ((ok, cols["ok"], "bien asignados"),
                            (nr, cols["nr"], "a revisión"),
                            (err, cols["err"], "mal asignados")):
            ax.barh(k, val, left=x0, color=c, edgecolor="white", linewidth=0.8,
                    label=lab if k == 0 else None)
            if val:
                ax.text(x0 + val / 2, k, str(val), ha="center", va="center",
                        fontsize=9.5, color="white" if c == cols["ok"] else "#333333")
            x0 += val

    ax.set_yticks(list(y))
    ax.set_yticklabels([ETIQ[r] for r in reglas], fontsize=11)
    ax.set_xlim(0, n)
    ax.set_xticks([0, 10, 20, n])
    ax.set_xlabel(f"Permisos de matrícula ambigua (n = {n})")
    ax.tick_params(length=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, -0.28), fontsize=9.5, handlelength=1.3)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(f"{OUT}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("->", OUT.with_suffix(".pdf"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
