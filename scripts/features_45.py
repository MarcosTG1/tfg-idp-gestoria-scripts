#!/usr/bin/env python3
"""Apartado 4.5: matriz de rasgos de los pares (permiso, carpeta candidata) para
los 29 permisos de matricula ambigua de la poblacion A, sobre la BASE DE
PRODUCCION.

Las carpetas candidatas de cada permiso se toman de Drive
(`drive_carpetas_createdtime.json`) y se restringen a las que EXISTIAN cuando el
permiso se archivo (`createdTime` <= momento de archivo, en
`drive_archivo_timestamps.json`). Es lo que ve el flujo en produccion. Cada fila
es un par (permiso, carpeta). `es_correcta` vale 1 solo para la carpeta exacta
del expediente correcto (por id de Drive; para homonimos se usa `gt_folder_id`).

Rasgos:
  temporales   mes_coincide_i1, es_mas_reciente_ct, es_mas_antigua_ct,
               dias_i1_vs_creacion, rango_dias_candidatas
  contenido    i1_literal_en_carpeta, bastidor_en_carpeta, titular_en_carpeta
  estructura   n_docs, tiene_pc_def, hay_otra_mismo_mes, n_candidatas

`es_mas_reciente_ct` es la senal que usa R1. Los rasgos de contenido y
`tiene_pc_def` estan favorecidos por como se construyo el conjunto (el permiso de
evaluacion se saco de su propia carpeta); se marcan como tales en la figura 4.5.

Salida: data/raw/dataset_eval/pares_45.csv
"""
import csv
import json
import re
import subprocess
from datetime import date, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
TREE = BASE / "A_a_expedientar"
OCRM = BASE / "ocr" / "mistral"
PRED = BASE / "prediccion_42.csv"
LABELS = BASE / "labels.csv"
DRIVE = BASE / "drive_carpetas_createdtime.json"
ARCHJS = BASE / "drive_archivo_timestamps.json"
OUT = BASE / "pares_45.csv"
DIAS_TOPE = 400


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


def a_fecha(s):
    m = re.match(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", s.strip())
    if not m:
        return None
    d, mth, y = (int(x) for x in m.groups())
    try:
        return date(y, mth, d)
    except ValueError:
        return None


def carpeta_local(nombre):
    for mes_dir in TREE.iterdir():
        p = mes_dir / nombre
        if p.is_dir():
            return p
    return None


def texto_local(p):
    if p is None:
        return ""
    out = []
    for f in p.iterdir():
        if f.suffix.lower() == ".pdf":
            out.append(subprocess.run(
                ["pdftotext", "-q", str(f), "-"], capture_output=True, text=True).stdout)
    return " ".join(out)


def main():
    pred = {r["id"]: r for r in csv.DictReader(PRED.read_text(encoding="utf-8").splitlines())}
    lab = {r["id"]: r for r in csv.DictReader(LABELS.read_text(encoding="utf-8-sig").splitlines(), delimiter=";")}
    amb = [i for i, p in pred.items()
           if p["poblacion"] == "A" and p["n_carpetas"] not in ("", "0", "1")]

    drive = json.loads(DRIVE.read_text())["carpetas"]
    por_mat = {}
    for f in drive:
        por_mat.setdefault(f["m"], []).append(f)
    aj = json.loads(ARCHJS.read_text())
    ARCH, GTID = aj["archivo"], aj["gt_folder_id"]

    filas = []
    for idn in amb:
        md = "\n".join(pg.get("markdown", "") for pg in json.loads((OCRM / f"{idn}.json").read_text())["pages"])
        mat = norm(pred[idn]["matricula_extraida"])
        i1_txt = campo(md, "I.1").strip()
        i1_f = a_fecha(i1_txt)
        i1_var = list(dict.fromkeys(
            v for v in (i1_txt, i1_txt.replace("-", "/"), i1_txt.replace("/", "-"))
            if re.match(r"\d{1,2}[-/]\d{1,2}[-/]\d{4}", v)))
        bastidor = norm(campo(md, "E"))
        c11 = campo(md, "C.1.1")
        apellido = norm(c11.split()[0]) if c11 else ""

        r = lab[idn]
        gn = r["carpeta_correcta"].strip()
        gmes = r["expediente_correcto"].split("/")[0]
        fs = por_mat.get(mat, [])
        if idn in GTID:
            gt_id = GTID[idn]
        else:
            cn = [f for f in fs if f["title"] == gn]
            gt = next((f for f in cn if ym(f["createdTime"]) == gmes), cn[0] if cn else None)
            gt_id = gt["id"] if gt else None

        limite_temporal = as_dt(ARCH[idn] + "T23:59:59+00:00")
        cand = sorted((f for f in fs if as_dt(f["createdTime"]) <= limite_temporal),
                      key=lambda f: f["createdTime"], reverse=True)
        if not cand:
            print(f"AVISO: {idn} sin candidatas <= T(P)")
            continue

        ct = {f["id"]: as_dt(f["createdTime"]) for f in cand}
        ct_max = max(ct.values())
        ct_min = min(ct.values())
        rango_dias = (ct_max - ct_min).days
        conteo_mes = {}
        for f in cand:
            conteo_mes[ym(f["createdTime"])] = conteo_mes.get(ym(f["createdTime"]), 0) + 1

        for f in cand:
            p_local = carpeta_local(f["title"])
            texto = texto_local(p_local)
            nombres = " ".join(x.name for x in p_local.iterdir()) if p_local else ""
            n_docs = sum(1 for _ in p_local.iterdir()) if p_local else 0
            fcre = ct[f["id"]].date()
            dias_i1_cre = abs((fcre - i1_f).days) if i1_f else DIAS_TOPE
            filas.append({
                "id": idn, "matricula": mat,
                "carpeta": f["title"], "carpeta_id": f["id"],
                "createdTime": f["createdTime"],
                "es_correcta": int(f["id"] == gt_id),
                # temporales (createdTime)
                "mes_coincide_i1": int(i1_f is not None and ym(f["createdTime"]) == f"{i1_f.year}-{i1_f.month:02d}"),
                "es_mas_reciente_ct": int(ct[f["id"]] == ct_max),
                "es_mas_antigua_ct": int(ct[f["id"]] == ct_min),
                "dias_i1_vs_creacion": min(dias_i1_cre, DIAS_TOPE),
                "rango_dias_candidatas": min(rango_dias, DIAS_TOPE),
                # contenido
                "i1_literal_en_carpeta": int(any(v in texto for v in i1_var)),
                "bastidor_en_carpeta": int(len(bastidor) >= 11 and bastidor in norm(texto)),
                "titular_en_carpeta": int(bool(apellido) and (apellido in norm(f["title"]) or apellido in norm(texto))),
                # estructura
                "n_docs": n_docs,
                "tiene_pc_def": int(bool(re.search(r"pc[ _-]*d(ef)?\b", nombres, re.I))),
                "hay_otra_mismo_mes": int(conteo_mes[ym(f["createdTime"])] > 1),
                "n_candidatas": len(cand),
            })

    campos = list(filas[0].keys())
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)
    npos = sum(f["es_correcta"] for f in filas)
    npermisos = len({f["id"] for f in filas})
    print(f"{len(filas)} pares ({npos} positivos) de {npermisos} permisos -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
