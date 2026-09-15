#!/usr/bin/env python3
"""Saca de la muestra las filas marcadas para excluir.

Para cada fila de labels.csv cuyo `categoria_resultado` empiece por "excluida":
  - la registra en excluidos.csv (id, poblacion, fichero, categoria, notas)
  - borra el PDF de data/raw/dataset_eval/muestra/<poblacion>/
  - la quita de labels.csv y de muestra.csv

Reejecutable: se puede llamar cada vez que se marquen nuevas filas.

Uso:  python scripts/excluir_muestras.py
"""
import csv
import io
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
LABELS = BASE / "labels.csv"
MUESTRA_CSV = BASE / "muestra.csv"
EXCLUIDOS = BASE / "excluidos.csv"
MUESTRA_DIR = BASE / "muestra"


def detectar_separador(texto):
    primera_linea = texto.splitlines()[0]
    return ";" if primera_linea.count(";") >= primera_linea.count(",") else ","


def leer(path):
    texto = path.read_text(encoding="utf-8-sig")
    separador = detectar_separador(texto)
    filas = list(csv.DictReader(texto.splitlines(), delimiter=separador))
    return filas, list(filas[0].keys()), separador


def escribir(path, filas, columnas, separador=";"):
    buf = io.StringIO()
    escritor = csv.DictWriter(buf, fieldnames=columnas, delimiter=separador, lineterminator="\r\n")
    escritor.writeheader()
    escritor.writerows(filas)
    path.write_text(buf.getvalue(), encoding="utf-8")


def main():
    rows, cols, sep_labels = leer(LABELS)
    fuera = [r for r in rows if r.get("categoria_resultado", "").startswith("excluida")]
    if not fuera:
        print("nada que excluir")
        return 0

    ya = set()
    nuevos = []
    if EXCLUIDOS.exists():
        prev, _, _ = leer(EXCLUIDOS)
        ya = {r["id"] for r in prev}
        nuevos = prev
    for r in fuera:
        if r["id"] in ya:
            continue
        nuevos.append({
            "id": r["id"], "poblacion": r["poblacion"], "fichero": r["fichero"],
            "categoria": r["categoria_resultado"], "notas": r.get("notas", ""),
        })
        pdf = MUESTRA_DIR / r["poblacion"] / r["fichero"]
        if pdf.exists():
            pdf.unlink()
            print(f"  borrado {pdf.relative_to(BASE)}")
        else:
            print(f"  (ya no estaba) {pdf.relative_to(BASE)}")

    escribir(EXCLUIDOS, nuevos, ["id", "poblacion", "fichero", "categoria", "notas"], ";")

    fuera_ids = {r["id"] for r in fuera}
    escribir(LABELS, [r for r in rows if r["id"] not in fuera_ids], cols, sep_labels)
    mrows, mcols, sep_muestra = leer(MUESTRA_CSV)
    escribir(MUESTRA_CSV, [r for r in mrows if r["id"] not in fuera_ids], mcols, sep_muestra)

    print(f"excluidas {len(fuera_ids)} filas -> {EXCLUIDOS.name}")
    print(f"labels.csv: {len(rows) - len(fuera_ids)} filas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
