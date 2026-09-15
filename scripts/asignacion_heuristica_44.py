#!/usr/bin/env python3
"""Apartado 4.4: heuristicas basadas en reglas para elegir expediente cuando la
matricula del permiso coincide con varias carpetas.

Se evaluan sobre los 29 permisos de la poblacion A cuya matricula aparece en mas
de una carpeta (el subconjunto ambiguo del apartado 4.2). Para cada uno se toman
del OCR de Mistral la fecha de expedicion (campo I.1); de la carpeta candidata,
su periodo AAAA-MM y el texto de los PDF que contiene (capa de texto, pdftotext).

Reglas, de menos a mas informacion:
  R1  carpeta mas reciente.
  R2  anclaje temporal: unica carpeta cuyo mes coincide con el de la fecha I.1;
      si no hay una sola, se recurre a R1.
  R3  R2 mas confirmacion por contenido: si la fecha I.1 aparece literal en la
      documentacion de una sola carpeta candidata, se elige esa.

El acierto se mide a nivel de carpeta (verdad de referencia v4.1, columna
`carpeta_correcta`). Como R1, R2 y R3 solo saben apuntar a un mes, cuando el mes
elegido contiene dos carpetas del mismo vehiculo la regla no puede nombrar una y
el permiso cuenta como "sin resolver".

Salida: docs/notes/aut_2/resultados_44.md (+ .json)
"""
import csv
import json
import re
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
TREE = BASE / "A_a_expedientar"
OCRM = BASE / "ocr" / "mistral"
PRED = BASE / "prediccion_42.csv"
LABELS = BASE / "labels.csv"
OUT = Path(__file__).resolve().parent.parent / "docs" / "notes" / "aut_2" / "resultados_44.md"

MES2026 = {"01", "02", "03", "04", "05"}


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def campo(md, clave):
    for linea in md.split("\n"):
        m = re.match(r"^\s*\|\s*\(?" + re.escape(clave) + r"\)?\s*\|\s*([^|]*?)\s*\|", linea)
        if m:
            return m.group(1).strip()
    return ""


def texto_carpeta(carpeta):
    trozos = []
    for f in carpeta.iterdir():
        if f.suffix.lower() == ".pdf":
            trozos.append(subprocess.run(
                ["pdftotext", "-q", str(f), "-"], capture_output=True, text=True).stdout)
    return " ".join(trozos)


def periodo(carpeta):
    mes = carpeta.parent.name
    return f"{'2026' if mes in MES2026 else '2025'}-{mes}"


def main():
    pred = {r["id"]: r for r in csv.DictReader(PRED.read_text(encoding="utf-8").splitlines())}
    lab = {r["id"]: r for r in csv.DictReader(LABELS.read_text(encoding="utf-8-sig").splitlines(), delimiter=";")}
    amb = [i for i, p in pred.items()
           if p["poblacion"] == "A" and p["n_carpetas"] not in ("", "0", "1")]

    tot = {"r1": 0, "r2": 0, "r3": 0}
    sinres = {"r1": 0, "r2": 0, "r3": 0}
    detalle = []

    for idn in amb:
        md = "\n".join(pg.get("markdown", "") for pg in json.loads((OCRM / f"{idn}.json").read_text())["pages"])
        mat = pred[idn]["matricula_extraida"]
        i1 = campo(md, "I.1").strip()
        i1_var = list(dict.fromkeys(
            v for v in (i1, i1.replace("-", "/"), i1.replace("/", "-"))
            if re.match(r"\d{2}[-/]\d{2}[-/]\d{4}", v)))
        mm = re.search(r"(\d{2})[-/](\d{2})[-/](\d{4})", i1)
        i1_mes = f"{mm.group(3)}-{mm.group(2)}" if mm else ""
        gt = lab[idn]["carpeta_correcta"].strip()

        cands = sorted(
            ((periodo(p), p) for p in TREE.glob("*/*")
             if p.is_dir() and norm(p.name).startswith(mat)),
            key=lambda t: t[0], reverse=True)
        per = [c[0] for c in cands]

        # una regla que apunta a un mes solo resuelve si ese mes tiene una carpeta
        def carpeta_de(p):
            enp = [c[1].name for c in cands if c[0] == p]
            return enp[0] if len(enp) == 1 else None

        p1 = per[0] if (len(per) == 1 or per[0] != per[1]) else None
        f1 = carpeta_de(p1) if p1 else None

        temp = [c for c in cands if c[0] == i1_mes]
        p2 = temp[0][0] if len(temp) == 1 else p1
        f2 = carpeta_de(p2) if p2 else None

        con_i1 = [c[1].name for c in cands if any(v in texto_carpeta(c[1]) for v in i1_var)]
        f3 = con_i1[0] if len(con_i1) == 1 else f2

        for k, f in (("r1", f1), ("r2", f2), ("r3", f3)):
            tot[k] += f == gt
            sinres[k] += f is None
        detalle.append({"id": idn, "matricula": mat, "n_carpetas": len(cands),
                        "i1": i1, "gt": gt, "r1": f1, "r2": f2, "r3": f3})

    n = len(amb)
    lineas_salida = ["# Resultados 4.4 - Asignacion de expediente por reglas (conjunto v4)\n",
         f"Generado por `scripts/asignacion_heuristica_44.py`. Subconjunto ambiguo: "
         f"{n} permisos de la poblacion A.\n",
         "| Regla | Aciertos | Exactitud | Sin resolver |",
         "|---|---|---|---|",
         f"| R1 carpeta mas reciente | {tot['r1']}/{n} | {100*tot['r1']/n:.1f}\\% | {sinres['r1']} |",
         f"| R2 anclaje por fecha de expedicion (I.1) | {tot['r2']}/{n} | {100*tot['r2']/n:.1f}\\% | {sinres['r2']} |",
         f"| R3 R2 + confirmacion por contenido | {tot['r3']}/{n} | {100*tot['r3']/n:.1f}\\% | {sinres['r3']} |",
         "",
         "Casos que R3 no resuelve o falla:"]
    for d in detalle:
        if d["r3"] != d["gt"]:
            lineas_salida.append(f"- {d['id']}  ({d['n_carpetas']} carpetas)  I.1={d['i1']}  "
                     f"esperado {d['gt']}  R3={d['r3']}")
    lineas_salida.append("")
    OUT.write_text("\n".join(lineas_salida), encoding="utf-8")
    OUT.with_suffix(".json").write_text(json.dumps(
        {"n": n, "aciertos": tot, "sin_resolver": sinres, "detalle": detalle}, indent=2), encoding="utf-8")
    print("\n".join(lineas_salida))
    print("->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
