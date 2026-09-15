#!/usr/bin/env python3
"""Apartado 4.4: asignacion de expediente evaluada sobre la BASE DE PRODUCCION.

A diferencia de la version offline (que comparaba contra el arbol de carpetas
congelado, con carpetas creadas despues del tramite), aqui las carpetas
candidatas de cada permiso se restringen a las que EXISTIAN cuando el permiso se
archivo, por su fecha real de creacion en Drive (`createdTime`). Es lo que ve el
flujo en produccion, que consulta Drive en vivo.

Datos:
  - data/raw/dataset_eval/drive_carpetas_createdtime.json   createdTime de cada
        carpeta de las 27 matriculas ambiguas (MCP de Google Drive, 2026-09-09).
  - data/raw/dataset_eval/drive_archivo_timestamps.json      momento de archivo
        T(P) = createdTime del PDF del permiso dentro de su carpeta ganadora.
  - data/raw/dataset_eval/labels.csv                         verdad de referencia
        (columna `carpeta_correcta`, enmienda v4.1).
  - OCR de Mistral de cada permiso                            para la fecha I.1.
  - arbol local A_a_expedientar/                              texto de las carpetas (R3).

Reglas (todas ordenan las candidatas por `createdTime` descendente, como el flujo):
  R1  la mas reciente por `createdTime`; si las DOS primeras estan en el mismo
      mes (AAAA-MM del `createdTime`), no decide -> a revision.
  R2  R1 mas anclaje: si una sola candidata tiene el mes de `createdTime` igual
      al mes de la fecha de expedicion (campo I.1), esa; si no, R1.
  R3  R2 mas confirmacion por contenido: si la fecha I.1 aparece literal en la
      documentacion de una sola candidata, esa; si no, R2.

Salida: docs/notes/aut_2/resultados_44.md (+ .json)
"""
import csv
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
TREE = BASE / "A_a_expedientar"
OCRM = BASE / "ocr" / "mistral"
PRED = BASE / "prediccion_42.csv"
LABELS = BASE / "labels.csv"
DRIVE = BASE / "drive_carpetas_createdtime.json"
ARCHJS = BASE / "drive_archivo_timestamps.json"
OUT = Path(__file__).resolve().parent.parent / "docs" / "notes" / "aut_2" / "resultados_44.md"


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def ym(iso):
    return iso[:7]


def as_dt(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def campo(md, clave):
    for linea in md.split("\n"):
        m = re.match(r"^\s*\|\s*\(?" + re.escape(clave) + r"\)?\s*\|\s*([^|]*?)\s*\|", linea)
        if m:
            return m.group(1).strip()
    return ""


def texto_local(mat, nombre_carpeta):
    """Texto de los PDF de la carpeta, buscada por nombre en el arbol local."""
    for mes_dir in TREE.iterdir():
        p = mes_dir / nombre_carpeta
        if p.is_dir():
            trozos = []
            for f in p.iterdir():
                if f.suffix.lower() == ".pdf":
                    trozos.append(subprocess.run(
                        ["pdftotext", "-q", str(f), "-"], capture_output=True, text=True).stdout)
            return " ".join(trozos)
    return ""


def main():
    pred = {r["id"]: r for r in csv.DictReader(PRED.read_text(encoding="utf-8").splitlines())}
    lab = {r["id"]: r for r in csv.DictReader(LABELS.read_text(encoding="utf-8-sig").splitlines(), delimiter=";")}
    amb = [i for i, p in pred.items()
           if p["poblacion"] == "A" and p["n_carpetas"] not in ("", "0", "1")]

    drive = json.loads(DRIVE.read_text())["carpetas"]
    for k, f in enumerate(drive):
        f["_k"] = k
    por_mat = {}
    for f in drive:
        por_mat.setdefault(f["m"], []).append(f)

    aj = json.loads(ARCHJS.read_text())
    ARCH = aj["archivo"]
    GTID = aj["gt_folder_id"]

    tot = {"r1": 0, "r2": 0, "r3": 0}
    rev = {"r1": 0, "r2": 0, "r3": 0}
    detalle = []

    for idn in sorted(amb):
        r = lab[idn]
        mat = norm(pred[idn]["matricula_extraida"])
        md = "\n".join(pg.get("markdown", "") for pg in json.loads((OCRM / f"{idn}.json").read_text())["pages"])
        i1 = campo(md, "I.1").strip()
        mm = re.search(r"(\d{2})[-/](\d{2})[-/](\d{4})", i1)
        i1_mes = f"{mm.group(3)}-{mm.group(2)}" if mm else ""
        i1_var = list(dict.fromkeys(
            v for v in (i1, i1.replace("-", "/"), i1.replace("/", "-"))
            if re.match(r"\d{2}[-/]\d{2}[-/]\d{4}", v)))

        gn = r["carpeta_correcta"].strip()
        gmes = r["expediente_correcto"].split("/")[0]
        fs = por_mat.get(mat, [])

        # carpeta ganadora concreta
        if idn in GTID:
            gt = next(f for f in fs if f["id"] == GTID[idn])
        else:
            cand_n = [f for f in fs if f["title"] == gn]
            gt = next((f for f in cand_n if ym(f["createdTime"]) == gmes), cand_n[0] if cand_n else None)

        # corte temporal: fin del dia del archivo real
        limite_temporal = as_dt(ARCH[idn] + "T23:59:59+00:00")
        cand = sorted((f for f in fs if as_dt(f["createdTime"]) <= limite_temporal),
                      key=lambda f: f["createdTime"], reverse=True)

        # R1
        if len(cand) >= 2 and ym(cand[0]["createdTime"]) == ym(cand[1]["createdTime"]):
            r1 = None
        else:
            r1 = cand[0]
        # R2
        del_mes = [f for f in cand if ym(f["createdTime"]) == i1_mes]
        r2 = del_mes[0] if len(del_mes) == 1 else r1
        # R3
        con_i1 = [f for f in cand if any(v in texto_local(mat, f["title"]) for v in i1_var)]
        r3 = con_i1[0] if len(con_i1) == 1 else r2

        picks = {"r1": r1, "r2": r2, "r3": r3}
        estado = {}
        for k, p in picks.items():
            if p is None:
                estado[k] = "revisar"
                rev[k] += 1
            elif p["_k"] == gt["_k"]:
                estado[k] = "ok"
                tot[k] += 1
            else:
                estado[k] = "mal"
        detalle.append({
            "id": idn, "i1": i1, "gt": f"{gmes}/{gn}",
            "n_candidatas": len(cand),
            "r1": estado["r1"], "r2": estado["r2"], "r3": estado["r3"],
            "pick_r1": (r1["title"] if r1 else None),
            "pick_r2": (r2["title"] if r2 else None),
            "pick_r3": (r3["title"] if r3 else None),
        })

    n = len(amb)
    mal = {k: n - tot[k] - rev[k] for k in tot}
    lineas_salida = ["# Resultados 4.4 - Asignacion de expediente (base de produccion, con `createdTime` real)\n",
         f"Generado por `scripts/asignacion_online_44.py`. {n} permisos de matricula "
         f"ambigua de la poblacion A. Candidatas restringidas a las carpetas con "
         f"`createdTime` <= momento de archivo del permiso (Drive). R1 es la regla del "
         f"flujo en produccion.\n",
         "| Regla | Bien | A revision | Mal | Exactitud |",
         "|---|---|---|---|---|",
         f"| R1 mas reciente por `createdTime` (flujo) | {tot['r1']} | {rev['r1']} | {mal['r1']} | {100*tot['r1']/n:.1f}\\% |",
         f"| R2 R1 + anclaje por mes de la fecha I.1 | {tot['r2']} | {rev['r2']} | {mal['r2']} | {100*tot['r2']/n:.1f}\\% |",
         f"| R3 R2 + confirmacion por contenido | {tot['r3']} | {rev['r3']} | {mal['r3']} | {100*tot['r3']/n:.1f}\\% |",
         "",
         "Detalle (permisos que alguna regla no coloca bien):"]
    for d in detalle:
        if not (d["r1"] == d["r2"] == d["r3"] == "ok"):
            lineas_salida.append(f"- {d['id']}  I.1={d['i1']}  gt={d['gt']}  "
                     f"R1={d['r1']}({d['pick_r1']})  R2={d['r2']}({d['pick_r2']})  R3={d['r3']}({d['pick_r3']})")
    lineas_salida.append("")
    OUT.write_text("\n".join(lineas_salida), encoding="utf-8")
    OUT.with_suffix(".json").write_text(json.dumps({
        "n": n,
        "base": "produccion (createdTime real, corte = momento de archivo)",
        "aciertos": tot,
        "sin_resolver": rev,   # = a revision
        "mal": mal,
        "detalle": detalle,
    }, indent=2), encoding="utf-8")
    print("\n".join(lineas_salida))
    print("->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
