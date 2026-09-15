#!/usr/bin/env python3
"""Metricas del apartado 4.2: evaluacion de la extraccion de matricula.

Cruza prediccion_42.csv con labels.csv y calcula:
  - exactitud de matricula (global, por formato, por poblacion, por via)
  - tasa de error de caracteres (CER) sobre el valor extraido
  - precision, exhaustividad y F1 de la lectura
  - matriz de confusion sobre las categorias de resultado (solo poblacion A)
  - lista de casos fallidos para el analisis cualitativo

Salida: docs/notes/aut_2/resultados_42.md  (tablas en markdown) y resumen por
consola.
"""
import csv
import re
import collections
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
DOCOUT = Path(__file__).resolve().parent.parent / "docs" / "notes" / "aut_2" / "resultados_42.md"


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def lev(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def leer_csv(ruta, delim=";"):
    return list(csv.DictReader(ruta.read_text(encoding="utf-8-sig").splitlines(), delimiter=delim))


def porcentaje(x, n):
    return f"{100*x/n:.1f}\\%" if n else "-"


def main():
    labels = {r["id"]: r for r in leer_csv(BASE / "labels.csv", ";")}
    pred = {r["id"]: r for r in leer_csv(BASE / "prediccion_42.csv", ",")}
    ids = [i for i in labels if i in pred]

    rows = []
    for i in ids:
        fila_label, fila_pred = labels[i], pred[i]
        ref = norm(fila_label["matricula_correcta"])
        hyp = norm(fila_pred["matricula_extraida"])
        rows.append({
            "id": i, "pob": fila_label["poblacion"], "fmt": fila_label["formato_matricula"],
            "via": fila_pred["leida_de"] or "(ninguna)",
            "ref": ref, "hyp": hyp, "exact": ref == hyp and ref != "",
            "d": lev(hyp, ref), "nref": len(ref),
            "cat_true": fila_label["categoria_resultado"], "cat_pred": fila_pred["categoria_predicha"],
        })

    n = len(rows)
    out = ["# Resultados 4.2 (generado por scripts/metricas_42.py)\n",
           f"Conjunto: v4, {n} permisos con OCR disponible "
           f"({sum(1 for r in rows if r['pob']=='A')} A + {sum(1 for r in rows if r['pob']=='B')} B).\n"]

    # --- exactitud global y desglosada ---
    def bloque(titulo, clave):
        out.append(f"\n## Exactitud de matricula por {titulo}\n")
        out.append("| grupo | n | exactas | exactitud | CER |")
        out.append("|---|---|---|---|---|")
        grupos = collections.defaultdict(list)
        for r in rows:
            grupos[r[clave]].append(r)
        for g in sorted(grupos):
            rs = grupos[g]
            ex = sum(x["exact"] for x in rs)
            cer = sum(x["d"] for x in rs) / max(1, sum(x["nref"] for x in rs))
            out.append(f"| {g} | {len(rs)} | {ex} | {porcentaje(ex,len(rs))} | {cer:.3f} |")
        ex = sum(x["exact"] for x in rows)
        cer = sum(x["d"] for x in rows) / max(1, sum(x["nref"] for x in rows))
        out.append(f"| **total** | {n} | {ex} | {porcentaje(ex,n)} | {cer:.3f} |")

    bloque("poblacion", "pob")
    bloque("formato de matricula", "fmt")
    bloque("via de lectura", "via")

    # --- precision / exhaustividad / F1 (lectura) ---
    tp = sum(1 for r in rows if r["exact"])
    emitidas = sum(1 for r in rows if r["hyp"])
    prec = tp / emitidas if emitidas else 0
    rec = tp / n
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
    out.append("\n## Precision, exhaustividad y F1 de la lectura\n")
    out.append(f"- matriculas emitidas: {emitidas}/{n}")
    out.append(f"- precision (de las emitidas, exactas): {prec*100:.1f}\\%")
    out.append(f"- exhaustividad (de las {n}, exactas): {rec*100:.1f}\\%")
    out.append(f"- F1: {f1*100:.1f}\\%")

    # --- matriz de confusion (poblacion A) ---
    A = [r for r in rows if r["pob"] == "A"]
    cats_t = sorted({r["cat_true"] for r in A})
    cats_p = sorted({r["cat_pred"] for r in A})
    out.append("\n## Matriz de confusion de categorias (poblacion A)\n")
    out.append("Filas = verdad de referencia, columnas = prediccion del pipeline reimplementado.\n")
    out.append("| verdad \\\\ pred | " + " | ".join(cats_p) + " | total |")
    out.append("|---" * (len(cats_p) + 2) + "|")
    M = collections.Counter((r["cat_true"], r["cat_pred"]) for r in A)
    for ct in cats_t:
        fila = [str(M[(ct, cp)]) for cp in cats_p]
        tot = sum(M[(ct, cp)] for cp in cats_p)
        out.append(f"| {ct} | " + " | ".join(fila) + f" | {tot} |")
    aciertos = sum(v for (ct, cp), v in M.items() if ct == cp)
    out.append(f"\nCoincidencia verdad = prediccion: {aciertos}/{len(A)} ({100*aciertos/len(A):.1f}\\%).")

    # --- analisis cualitativo: casos fallidos ---
    fallos = [r for r in rows if not r["exact"]]
    out.append(f"\n## Casos con matricula no exacta ({len(fallos)}/{n})\n")
    out.append("| id | pob | formato | via | referencia | extraida | dist |")
    out.append("|---|---|---|---|---|---|---|")
    for r in sorted(fallos, key=lambda x: (x["fmt"], x["id"])):
        out.append(f"| {r['id']} | {r['pob']} | {r['fmt']} | {r['via']} | {r['ref']} | {r['hyp'] or '(vacio)'} | {r['d']} |")

    DOCOUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out[:40]))
    print(f"\n-> {DOCOUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
