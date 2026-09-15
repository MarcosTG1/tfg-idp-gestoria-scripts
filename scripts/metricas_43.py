#!/usr/bin/env python3
"""Metricas del apartado 4.3: compara Mistral OCR con los motores de codigo
abierto del banco (Tesseract, PaddleOCR, docTR) sobre los 231 permisos del
conjunto v4.

Para cada motor se mide la lectura de la matricula de dos formas:
  - "estructura + barrido": la logica completa de `extraer_offline.leer_matricula`
    (capa 1 sobre la fila del campo A si el motor da esa estructura, y si no,
    barrido del texto). Es la que se beneficia de que Mistral devuelva la tabla.
  - "solo barrido": se ignora cualquier fila de campo A y se aplica unicamente
    el barrido de patrones de matricula. Aisla el acierto de caracteres del
    motor, sin premiar la recuperacion de estructura.

Ademas: CER de la matricula, y latencia mediana / p90 a partir de los
timing.csv del banco.

Salida: docs/notes/aut_2/resultados_43.md
"""
import csv
import json
import re
import statistics as st
from pathlib import Path

import extraer_offline as ex  # mismo directorio scripts/

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
OCR = BASE / "ocr"
LABELS = BASE / "labels.csv"
SALIDA = Path(__file__).resolve().parent.parent / "docs" / "notes" / "aut_2" / "resultados_43.md"

MOTORES = ["mistral", "tesseract", "paddleocr", "doctr"]

# patrones de barrido, identicos a los de extraer_offline / nodo en produccion
PATRONES_BARRIDO = [
    re.compile(r"\b" + ex.cuerpoEspecial + r"\b"),
    re.compile(r"\b" + ex.cuerpoTemporal + r"\b"),
    re.compile(r"\b" + ex.cuerpoModerna + r"\b"),
    re.compile(r"\b" + ex.cuerpoAntigua + r"\b"),
]


def texto_motor(motor, idn):
    if motor == "mistral":
        p = OCR / "mistral" / f"{idn}.json"
        if not p.exists():
            return None
        pages = json.loads(p.read_text(encoding="utf-8")).get("pages", [])
        return "\n".join(pg.get("markdown", "") or "" for pg in pages)
    p = OCR / motor / f"{idn}.txt"
    return p.read_text(encoding="utf-8") if p.exists() else None


def lee_estructura(texto):
    return ex.leer_matricula([{"markdown": texto}])["matricula"]


def lee_barrido(texto):
    t = texto.upper()
    vistos = []
    rangos = []
    for patron in PATRONES_BARRIDO:
        for m in patron.finditer(t):
            ini, fin = m.start(), m.end()
            if any(ini < b and fin > a for a, b in rangos):
                continue
            antes = re.split(r"[\n|]", t[max(0, ini - 24):ini])[-1]
            despues = re.split(r"[\n|]", t[fin:fin + 24])[0]
            if re.search(r"[A-Z0-9]{6,}$", re.sub(r"[^A-Z0-9]", "", antes)):
                continue
            if re.match(r"^[A-Z0-9]{6,}", re.sub(r"[^A-Z0-9]", "", despues)):
                continue
            rangos.append((ini, fin))
            cand = "".join(m.groups())
            if cand not in vistos:
                vistos.append(cand)
    return vistos[0] if len(vistos) == 1 else ""


def cer(hyp, ref):
    a, b = ref, hyp
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[len(b)]


def latencias(motor):
    p = OCR / motor / "timing.csv"
    if not p.exists():
        return None
    segs = [float(r["segundos"]) for r in csv.DictReader(p.read_text().splitlines())]
    if not segs:
        return None
    segs.sort()
    p90 = segs[min(len(segs) - 1, int(round(0.9 * (len(segs) - 1))))]
    return st.median(segs), p90, len(segs)


def main():
    lab = list(csv.DictReader(LABELS.read_text(encoding="utf-8-sig").splitlines(), delimiter=";"))
    formatos = sorted({r["formato_matricula"] for r in lab})

    # resultados[motor][variante] = {"tot":..,"ok":..,"cer_num":..,"cer_den":..,
    #                                "por_formato": {fmt:[ok,tot]}, "emitidas":..}
    res = {}
    disponibles = []
    for motor in MOTORES:
        if all(texto_motor(motor, r["id"]) is None for r in lab[:5]):
            continue
        disponibles.append(motor)
        for var in ("estructura", "barrido"):
            res[(motor, var)] = {
                "tot": 0, "ok": 0, "emit": 0, "cn": 0, "cd": 0,
                "pf": {f: [0, 0] for f in formatos},
            }

    faltan = {m: 0 for m in disponibles}
    for r in lab:
        idn, ref = r["id"], ex.norm(r["matricula_correcta"])
        fmt = r["formato_matricula"]
        for motor in disponibles:
            txt = texto_motor(motor, idn)
            if txt is None:
                faltan[motor] += 1
                continue
            for var, fn in (("estructura", lee_estructura), ("barrido", lee_barrido)):
                got = ex.norm(fn(txt))
                d = res[(motor, var)]
                d["tot"] += 1
                d["pf"][fmt][1] += 1
                if got:
                    d["emit"] += 1
                if got == ref:
                    d["ok"] += 1
                    d["pf"][fmt][0] += 1
                d["cn"] += cer(got, ref)
                d["cd"] += len(ref)

    lineas_salida = []
    lineas_salida.append("# Resultados 4.3 - Comparativa de motores de OCR (conjunto v4)\n")
    lineas_salida.append("Generado por `scripts/metricas_43.py`. 231 permisos (158 A + 73 B).\n")
    lineas_salida.append(f"Motores con salida disponible: {', '.join(disponibles)}.")
    if any(faltan.values()):
        lineas_salida.append(f"Permisos sin salida por motor: {faltan}.")
    lineas_salida.append("")

    lineas_salida.append("## Exactitud de matricula y CER\n")
    lineas_salida.append("| motor | variante | exactas | exactitud | CER | emitidas |")
    lineas_salida.append("|---|---|---|---|---|---|")
    for motor in disponibles:
        for var in ("estructura", "barrido"):
            d = res[(motor, var)]
            ex_pct = 100 * d["ok"] / d["tot"] if d["tot"] else 0
            cer_v = d["cn"] / d["cd"] if d["cd"] else 0
            lineas_salida.append(f"| {motor} | {var} | {d['ok']}/{d['tot']} | "
                     f"{ex_pct:.1f}\\% | {cer_v:.3f} | {d['emit']}/{d['tot']} |")
    lineas_salida.append("")

    lineas_salida.append("## Exactitud por formato de matricula (variante estructura + barrido)\n")
    lineas_salida.append("| formato | " + " | ".join(disponibles) + " |")
    lineas_salida.append("|" + "---|" * (len(disponibles) + 1))
    for f in formatos:
        fila = [f]
        for motor in disponibles:
            ok, tot = res[(motor, "estructura")]["pf"][f]
            fila.append(f"{ok}/{tot}" + (f" ({100*ok/tot:.0f}\\%)" if tot else ""))
        lineas_salida.append("| " + " | ".join(fila) + " |")
    lineas_salida.append("")

    lineas_salida.append("## Latencia por permiso (proceso local; Mistral es ida y vuelta de red)\n")
    lineas_salida.append("| motor | mediana (s) | p90 (s) | n |")
    lineas_salida.append("|---|---|---|---|")
    for motor in disponibles:
        lat = latencias(motor)
        if lat:
            lineas_salida.append(f"| {motor} | {lat[0]:.2f} | {lat[1]:.2f} | {lat[2]} |")
        else:
            lineas_salida.append(f"| {motor} | n/d | n/d | - |")
    lineas_salida.append("")
    lineas_salida.append("## Coste\n")
    lineas_salida.append("- Mistral OCR: precio de lista publico de la API (del orden de "
             "1 USD por cada 1000 paginas; citar la pagina de precios en la memoria).")
    lineas_salida.append("- Tesseract, PaddleOCR, docTR: coste marginal 0, ejecucion en CPU local.")
    lineas_salida.append("")

    SALIDA.write_text("\n".join(lineas_salida), encoding="utf-8")

    resumen = {"motores": disponibles, "formatos": formatos, "datos": {}}
    for motor in disponibles:
        resumen["datos"][motor] = {}
        for var in ("estructura", "barrido"):
            d = res[(motor, var)]
            lat = latencias(motor)
            resumen["datos"][motor][var] = {
                "ok": d["ok"], "tot": d["tot"], "emit": d["emit"],
                "exactitud": 100 * d["ok"] / d["tot"] if d["tot"] else 0,
                "cer": d["cn"] / d["cd"] if d["cd"] else 0,
                "por_formato": {f: d["pf"][f] for f in formatos},
                "lat_mediana": lat[0] if lat else None,
                "lat_p90": lat[1] if lat else None,
            }
    SALIDA.with_suffix(".json").write_text(json.dumps(resumen, indent=2), encoding="utf-8")

    print("\n".join(lineas_salida))
    print("\n->", SALIDA, "y", SALIDA.with_suffix(".json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
