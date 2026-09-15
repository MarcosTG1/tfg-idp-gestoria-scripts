#!/usr/bin/env python3
"""Rasgos objetivos de cada PDF de data/raw/dataset_eval/muestra/ (los que se
pueden sacar sin leer el contenido). Ayudan a rellenar `calidad_escaneo` y
`modelo_documento` de labels_plantilla.csv, pero NO los sustituyen.

Salida: data/raw/dataset_eval/rasgos_pdf.csv  (clave de union: id)

Uso:  python scripts/rasgos_pdf.py
"""
import csv
import re
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
MUESTRA = BASE / "muestra"
SALIDA = BASE / "rasgos_pdf.csv"


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return ""


def rasgos(pdf):
    info = run(["pdfinfo", str(pdf)])
    m = re.search(r"^Pages:\s+(\d+)", info, re.M)
    paginas = int(m.group(1)) if m else 0
    m = re.search(r"^Page size:\s+(.+)$", info, re.M)
    page_size = m.group(1).strip() if m else ""

    texto = run(["pdftotext", "-q", str(pdf), "-"]).strip()
    tiene_texto = "si" if len(texto) > 40 else "no"

    lineas_imagenes = run(["pdfimages", "-list", str(pdf)]).splitlines()
    dpis, anchos, altos, n_img = [], [], [], 0
    for linea in lineas_imagenes[2:]:
        columnas = linea.split()
        if len(columnas) < 15:
            continue
        n_img += 1
        try:
            anchos.append(int(columnas[3]))
            altos.append(int(columnas[4]))
            dpi_x, dpi_y = columnas[12], columnas[13]
            for valor_dpi in (dpi_x, dpi_y):
                if valor_dpi not in ("-", ""):
                    dpis.append(int(round(float(valor_dpi))))
        except ValueError:
            pass

    return {
        "paginas": paginas,
        "page_size": page_size,
        "tiene_capa_texto": tiene_texto,
        "n_imagenes": n_img,
        "dpi_min": min(dpis) if dpis else "",
        "dpi_max": max(dpis) if dpis else "",
        "img_ancho_max": max(anchos) if anchos else "",
        "img_alto_max": max(altos) if altos else "",
        "bytes": pdf.stat().st_size,
    }


def main():
    filas = []
    for pdf in sorted(MUESTRA.rglob("*.pdf")):
        r = {"id": pdf.stem, "poblacion": pdf.parent.name, "fichero": pdf.name}
        r.update(rasgos(pdf))
        filas.append(r)
    with SALIDA.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    con_dpi = [f["dpi_max"] for f in filas if f["dpi_max"] != ""]
    print(f"{len(filas)} PDF -> {SALIDA}")
    if con_dpi:
        print(f"  dpi_max: min={min(con_dpi)} mediana~{sorted(con_dpi)[len(con_dpi)//2]} max={max(con_dpi)}")
    print(f"  con capa de texto: {sum(1 for f in filas if f['tiene_capa_texto']=='si')}/{len(filas)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
