#!/usr/bin/env python3
"""Enmienda v4 -> v4.1 del conjunto de evaluacion.

Anade a data/raw/dataset_eval/labels.csv la columna `carpeta_correcta`, que fija
la carpeta EXACTA del expediente (no solo el mes AAAA-MM) para los 29 permisos de
matricula ambigua de la poblacion A (los que aparecen en mas de una carpeta).

En 26 de esos 29 permisos, el mes del expediente correcto contiene una unica
carpeta candidata y la carpeta queda determinada. En los 3 restantes hay dos
carpetas del mismo vehiculo abiertas el mismo mes; para ellos se registra la
carpeta indicada por la gestoria (diccionario DESAMB).

El resto de filas quedan con `carpeta_correcta` vacia: su `expediente_correcto`
a nivel de mes ya identifica una sola carpeta.

Nota: las matriculas y los nombres de carpeta de DESAMB estan anonimizados
(no son los reales del archivo de la gestoria); conservan el formato y la
relacion 1 a 1 del caso real descrito en el apartado 4.4 de la memoria.
"""
import csv
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
TREE = BASE / "A_a_expedientar"
PRED = BASE / "prediccion_42.csv"
LAB = BASE / "labels.csv"
MES2026 = {"01", "02", "03", "04", "05"}

DESAMB = {
    "01__7042MKX__pc-d": "7042MKX CLIENTE A",
    "02__7042MKX__pc-d": "7042MKX CLIENTE A",
    "02__3168NRP__pc-def": "3168NRP CLIENTE B TRANSPORTE",
}


def norm(texto):
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def periodo(carpeta):
    mes = carpeta.parent.name
    anio = "2026" if mes in MES2026 else "2025"
    return f"{anio}-{mes}"


def main():
    pred = {r["id"]: r for r in csv.DictReader(PRED.read_text(encoding="utf-8").splitlines())}
    ambiguos = [i for i, p in pred.items()
                if p["poblacion"] == "A" and p["n_carpetas"] not in ("", "0", "1")]

    rows = list(csv.DictReader(LAB.read_text(encoding="utf-8-sig").splitlines(), delimiter=";"))
    campos = list(rows[0].keys())
    if "carpeta_correcta" not in campos:
        campos.insert(campos.index("origen_expediente"), "carpeta_correcta")
    for r in rows:
        r.setdefault("carpeta_correcta", "")
    by_id = {r["id"]: r for r in rows}

    resultado = []
    for permiso_id in ambiguos:
        r = by_id[permiso_id]
        matricula = norm(pred[permiso_id]["matricula_extraida"])
        mes_correcto = r["expediente_correcto"].split("/")[0]
        carpetas_del_mes = sorted(
            carpeta.name for carpeta in TREE.glob("*/*")
            if carpeta.is_dir() and norm(carpeta.name).startswith(matricula) and periodo(carpeta) == mes_correcto
        )
        if permiso_id in DESAMB:
            elegida = DESAMB[permiso_id]
            assert elegida in carpetas_del_mes, (permiso_id, elegida, carpetas_del_mes)
        elif len(carpetas_del_mes) == 1:
            elegida = carpetas_del_mes[0]
        else:
            raise SystemExit(f"sin resolver: {permiso_id} {mes_correcto} -> {carpetas_del_mes}")
        r["carpeta_correcta"] = elegida
        resultado.append((permiso_id, mes_correcto, elegida, len(carpetas_del_mes)))

    with LAB.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, delimiter=";")
        w.writeheader()
        w.writerows(rows)

    print(f"{len(resultado)}/29 permisos ambiguos con carpeta_correcta fijada\n")
    for permiso_id, mes_correcto, carpeta_elegida, n_candidatas in resultado:
        marca = "   <- desambiguacion manual (2 carpetas del mismo mes)" if n_candidatas > 1 else ""
        print(f"  {permiso_id:24s} {mes_correcto}  ->  {carpeta_elegida}{marca}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
