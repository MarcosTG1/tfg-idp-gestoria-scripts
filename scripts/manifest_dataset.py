#!/usr/bin/env python3
"""Recorre data/raw/dataset_eval/ y escribe un manifiesto CSV del conjunto de
evaluacion del Capitulo 4.

Uso:
    python scripts/manifest_dataset.py

No lee el contenido de los PDF ni deduce la verdad de referencia: solo
inventaria lo descargado. La matricula correcta, la categoria y (para la
poblacion A) el expediente correcto se anotan despues a mano en labels.csv.
"""
import csv
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
SALIDA = RAIZ / "manifest.csv"

# subcarpeta de primer nivel -> etiqueta de poblacion
#   A_permisos      : permisos definitivos ya extraidos de los expedientes
#   A_a_expedientar : descarga bruta de carpetas de expediente (evidencia para
#                     la verdad de referencia), NO se inventaria aqui
POBLACIONES = {
    "A_permisos": "A",
    "B_entregados": "B",
    "fallos_pendientes": "fallo",
}


def sha1_corto(ruta):
    h = hashlib.sha1()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()[:12]


def main():
    if not RAIZ.exists():
        print(f"No existe {RAIZ}", file=sys.stderr)
        return 1

    filas = []
    for sub, poblacion in POBLACIONES.items():
        base = RAIZ / sub
        if not base.exists():
            continue
        for pdf in sorted(base.rglob("*.pdf")):
            rel = pdf.relative_to(RAIZ)
            h = sha1_corto(pdf)
            filas.append(
                {
                    "id": f"{poblacion}_{h}",
                    "poblacion": poblacion,
                    "ruta_local": str(rel),
                    "nombre_original": pdf.name,
                    "subcarpeta": str(rel.parent),
                    "bytes": pdf.stat().st_size,
                    "sha1_12": h,
                }
            )

    with SALIDA.open("w", newline="", encoding="utf-8") as fh:
        campos = [
            "id",
            "poblacion",
            "ruta_local",
            "nombre_original",
            "subcarpeta",
            "bytes",
            "sha1_12",
        ]
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)

    por_pob = {}
    for f in filas:
        por_pob[f["poblacion"]] = por_pob.get(f["poblacion"], 0) + 1

    sello = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{sello}] {len(filas)} PDF -> {SALIDA}")
    for p, n in sorted(por_pob.items()):
        print(f"  poblacion {p}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
