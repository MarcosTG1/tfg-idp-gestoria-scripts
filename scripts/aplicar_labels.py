#!/usr/bin/env python3
"""Vuelca labels_editados.json en data/raw/dataset_eval/labels.csv.

El JSON tiene la forma {id: {campo: valor, ...}} y solo se tocan las filas
que aparecen en el JSON, y solo las columnas de la verdad de referencia.
Se conserva el separador ';' y el salto de linea CRLF del CSV original.
"""

import csv
import io
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
RUTA_CSV = BASE / "labels.csv"
RUTA_JSON = Path(__file__).resolve().parent.parent / "labels_editados.json"

COLUMNAS_EDITABLES = [
    "matricula_correcta", "modelo_documento", "calidad_escaneo",
    "categoria_resultado", "expediente_correcto", "origen_expediente",
    "fecha_incorporacion", "notas",
]


def main():
    cambios = json.loads(RUTA_JSON.read_text(encoding="utf-8"))
    filas = list(csv.DictReader(RUTA_CSV.read_text(encoding="utf-8-sig").splitlines(), delimiter=";"))
    nombres_columnas = list(filas[0].keys())

    filas_tocadas = 0
    for fila in filas:
        cambios_fila = cambios.get(fila["id"])
        if not cambios_fila:
            continue
        for columna in COLUMNAS_EDITABLES:
            if columna in cambios_fila and cambios_fila[columna] != "":
                valor_nuevo = cambios_fila[columna]
                if ";" in str(valor_nuevo) or "\n" in str(valor_nuevo):
                    raise SystemExit(f"valor con ';' o salto de linea en {fila['id']}::{columna}")
                fila[columna] = valor_nuevo
        filas_tocadas += 1

    salida = io.StringIO()
    escritor = csv.DictWriter(salida, fieldnames=nombres_columnas, delimiter=";", lineterminator="\r\n")
    escritor.writeheader()
    escritor.writerows(filas)
    RUTA_CSV.write_text(salida.getvalue(), encoding="utf-8")

    sin_matricula = sum(1 for fila in filas if fila["matricula_correcta"] == "")
    print(f"filas actualizadas: {filas_tocadas}/{len(filas)}  (sin matricula_correcta: {sin_matricula})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
