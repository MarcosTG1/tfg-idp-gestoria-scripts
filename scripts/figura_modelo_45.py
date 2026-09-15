#!/usr/bin/env python3
"""Figuras del apartado 4.5:
  memoria/figs/modelo-comparativa.{pdf,png}  - reglas frente a modelo, sobre los
      29 permisos ambiguos (barras apiladas: bien / sin resolver / mal).
  memoria/figs/modelo-coeficientes.{pdf,png} - coeficientes de la regresion
      logistica (media de los 29 pliegues, rasgos estandarizados).

Lee docs/notes/aut_2/resultados_45.json.  Uso:  python scripts/figura_modelo_45.py
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DATOS = ROOT / "docs" / "notes" / "aut_2" / "resultados_45.json"
FIGS = ROOT / "memoria" / "figs"

RASGO_ES = {
    "mes_coincide_i1": "mes de creación de la carpeta = mes del campo I.1",
    "n_docs": "nº de documentos de la carpeta",
    "titular_en_carpeta": "titular presente en la carpeta",
    "tiene_pc_def": "la carpeta tiene un permiso definitivo",
    "es_mas_reciente_ct": "es la carpeta creada más recientemente",
    "i1_literal_en_carpeta": "fecha I.1 literal en la carpeta",
    "es_mas_antigua_ct": "es la carpeta creada más antigua",
    "n_candidatas": "nº de carpetas candidatas",
    "hay_otra_mismo_mes": "hay otra candidata creada el mismo mes",
    "dias_i1_vs_creacion": "días entre I.1 y la creación de la carpeta",
    "rango_dias_candidatas": "rango en días entre creación de candidatas",
    "bastidor_en_carpeta": "bastidor presente en la carpeta",
}

PLT = {"font.family": "STIXGeneral", "mathtext.fontset": "stix",
       "font.size": 10.5, "axes.linewidth": 0.6}


def comparativa(d):
    n = d["n"]
    filas = [
        ("R1", d["reglas"]["r1"]),
        ("R2", d["reglas"]["r2"]),
        ("R3", d["reglas"]["r3"]),
        ("Árbol (prof. 2)", d["arbol"]),
        ("Reg. logística", {"ok": d["lr"]["bien"], "sin_resolver": 0, "mal": d["lr"]["mal"]}),
    ]
    plt.rcParams.update(PLT)
    fig, ax = plt.subplots(figsize=(6.7, 2.9))
    cols = {"ok": "#2166ac", "nr": "#c9d7e6", "err": "#e8a0a0"}
    for k, (lab, r) in enumerate(reversed(filas)):
        ok = r.get("ok", r.get("bien", 0))
        nr = r.get("sin_resolver", 0)
        err = r.get("mal", 0)
        x0 = 0
        for val, c, lg in ((ok, cols["ok"], "bien asignados"),
                           (nr, cols["nr"], "a revisión"),
                           (err, cols["err"], "mal asignados")):
            ax.barh(k, val, left=x0, color=c, edgecolor="white", linewidth=0.8,
                    label=lg if k == 0 else None)
            if val:
                ax.text(x0 + val / 2, k, str(val), ha="center", va="center",
                        fontsize=9.5, color="white" if c == cols["ok"] else "#333333")
            x0 += val
    ax.set_yticks(range(len(filas)))
    ax.set_yticklabels([lab for lab, _ in reversed(filas)], fontsize=10.5)
    ax.set_xlim(0, n)
    ax.set_xticks([0, 10, 20, n])
    ax.set_xlabel(f"Permisos de matrícula ambigua (n = {n})")
    ax.tick_params(length=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, -0.24), fontsize=9.5, handlelength=1.3)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(FIGS / f"modelo-comparativa.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


CONSTRUCCION = {"i1_literal_en_carpeta", "titular_en_carpeta", "tiene_pc_def"}


def coeficientes(d):
    items = list(d["coeficientes"].items())
    items.sort(key=lambda t: t[1])  # de negativo a positivo, de abajo a arriba
    nombres = [RASGO_ES.get(k, k) for k, _ in items]
    vals = [v for _, v in items]
    favor = [k in CONSTRUCCION for k, _ in items]
    plt.rcParams.update(PLT)
    fig, ax = plt.subplots(figsize=(6.7, 3.7))
    cols = ["#c0504d" if v < 0 else "#2166ac" for v in vals]
    bars = ax.barh(range(len(vals)), vals, color=cols, edgecolor="white", linewidth=0.5)
    for b, f in zip(bars, favor):
        if f:
            b.set_hatch("////")
            b.set_edgecolor("#ffffff")
    ax.axvline(0, color="#333333", linewidth=0.7)
    ax.set_yticks(range(len(vals)))
    ax.set_yticklabels([f"{n} *" if f else n for n, f in zip(nombres, favor)], fontsize=9.5)
    ax.set_xlabel("Coeficiente (features estandarizados)")
    ax.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{x:g}".replace("-", "−").replace(".", ",")))
    ax.tick_params(length=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color="#dddddd", linewidth=0.6)
    ax.set_axisbelow(True)
    for i, v in enumerate(vals):
        ax.text(v + (0.05 if v >= 0 else -0.05), i, f"{v:+.2f}".replace(".", ","),
                ha="left" if v >= 0 else "right", va="center", fontsize=8.5, color="#333333")
    ax.set_xlim(min(vals) - 0.45, max(vals) + 0.45)
    fig.text(0.5, -0.02,
             "*  feature favorecido por la construcción del conjunto (ver apartado 4.5)",
             ha="center", fontsize=8.5, style="italic", color="#555555")
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(FIGS / f"modelo-coeficientes.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    d = json.loads(DATOS.read_text())
    comparativa(d)
    coeficientes(d)
    print("->", FIGS / "modelo-comparativa.pdf", "y", FIGS / "modelo-coeficientes.pdf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
