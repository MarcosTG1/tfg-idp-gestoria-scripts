#!/usr/bin/env python3
"""Muestra estratificada y reproducible del conjunto de evaluacion (Cap. 4).

Entrada:
  data/raw/dataset_eval/A_permisos/_extraccion.csv   (poblacion A ya extraida)
  data/raw/dataset_eval/B_entregados/**/*.pdf         (poblacion B, reserva)

Salida (todo bajo data/raw/dataset_eval/, no versionado):
  muestra/A/*.pdf , muestra/B/*.pdf   copias de los seleccionados
  muestra.csv                          lista congelada con la semilla
  labels_plantilla.csv                 una fila por permiso, con las columnas
                                       derivables rellenas y las de verdad de
                                       referencia en blanco para anotar a mano

Uso:
    python scripts/muestrear.py [--seed 20260907] [--moderna 100] [--b 50]
"""
import argparse
import csv
import random
import re
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
A_CSV = BASE / "A_permisos" / "_extraccion.csv"
A_DIR = BASE / "A_permisos"
B_DIR = BASE / "B_entregados"
OUT = BASE / "muestra"

RE_MODERNA = re.compile(r"^\d{4}[A-Z]{3}$")
RE_VERDE = re.compile(r"^[A-Z]\d{4}B[A-Z]{2}$")            # P0123BAA, R9876BZZ
RE_PROVINCIAL = re.compile(r"^[A-Z]{1,2}\d{3,6}[A-Z]{0,2}$")  # V1234AB, TO5678CD, B123456


def formato(token):
    if not token:
        return "sin_token"
    if RE_MODERNA.match(token):
        return "moderna"
    if RE_VERDE.match(token):
        return "placa_verde"
    if RE_PROVINCIAL.match(token):
        return "provincial"
    return "otro"


def cargar_A():
    filas = []
    for r in csv.DictReader(A_CSV.open(encoding="utf-8")):
        if r["estado"] == "revisar_sin_pc":
            continue
        r["formato"] = formato(r["matricula_token"])
        r["ruta"] = A_DIR / r["fichero_destino"]
        if r["ruta"].exists():
            filas.append(r)
    return filas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260907)
    ap.add_argument("--moderna", type=int, default=100, help="cupo de matricula moderna en A")
    ap.add_argument("--b", type=int, default=50, help="tamano de muestra de poblacion B")
    args = ap.parse_args()
    rnd = random.Random(args.seed)

    a = cargar_A()
    por_fmt = {}
    for r in a:
        por_fmt.setdefault(r["formato"], []).append(r)

    seleccion_a = []
    for fmt, filas in por_fmt.items():
        if fmt == "moderna":
            filas = sorted(filas, key=lambda r: r["ruta"].name)
            rnd.shuffle(filas)
            seleccion_a += filas[: args.moderna]
        else:
            seleccion_a += filas  # provincial, placa_verde, otro, sin_token: todos

    b_todos = sorted(B_DIR.rglob("*.pdf"), key=lambda p: str(p))
    seleccion_b = rnd.sample(b_todos, min(args.b, len(b_todos)))

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "A").mkdir(parents=True)
    (OUT / "B").mkdir(parents=True)

    muestra_rows, label_rows = [], []
    for r in sorted(seleccion_a, key=lambda r: r["ruta"].name):
        dst = OUT / "A" / r["ruta"].name
        shutil.copy2(r["ruta"], dst)
        muestra_rows.append(
            {
                "id": dst.stem,
                "poblacion": "A",
                "fichero": dst.name,
                "mes": r["mes"],
                "carpeta_expediente": r["carpeta_expediente"],
                "formato_estimado": r["formato"],
                "matricula_token_carpeta": r["matricula_token"],
                "estado_extraccion": r["estado"],
                "seed": args.seed,
            }
        )
        label_rows.append(
            {
                "id": dst.stem,
                "poblacion": "A",
                "fichero": dst.name,
                "formato_estimado": r["formato"],
                "matricula_token_carpeta": r["matricula_token"],
                "matricula_correcta": "",
                "modelo_documento": "",
                "calidad_escaneo": "",
                "anotacion_manuscrita": "no",
                "categoria_resultado": "",
                "expediente_correcto": "",
                "origen_expediente": "",
                "fecha_incorporacion": "",
                "notas": "",
            }
        )

    for p in sorted(seleccion_b, key=lambda p: p.name):
        anio = p.parent.name
        dst = OUT / "B" / f"{anio.split()[-1]}__{p.name}"
        shutil.copy2(p, dst)
        muestra_rows.append(
            {
                "id": dst.stem,
                "poblacion": "B",
                "fichero": dst.name,
                "mes": "",
                "carpeta_expediente": anio,
                "formato_estimado": "",
                "matricula_token_carpeta": "",
                "estado_extraccion": "",
                "seed": args.seed,
            }
        )
        label_rows.append(
            {
                "id": dst.stem,
                "poblacion": "B",
                "fichero": dst.name,
                "formato_estimado": "",
                "matricula_token_carpeta": "",
                "matricula_correcta": "",
                "modelo_documento": "",
                "calidad_escaneo": "",
                "anotacion_manuscrita": "si",
                "categoria_resultado": "",
                "expediente_correcto": "",
                "origen_expediente": "",
                "fecha_incorporacion": "",
                "notas": "",
            }
        )

    with (BASE / "muestra.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(muestra_rows[0].keys()))
        w.writeheader()
        w.writerows(muestra_rows)
    with (BASE / "labels_plantilla.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(label_rows[0].keys()))
        w.writeheader()
        w.writerows(label_rows)

    na = sum(1 for r in muestra_rows if r["poblacion"] == "A")
    nb = sum(1 for r in muestra_rows if r["poblacion"] == "B")
    print(f"semilla {args.seed}")
    resumen_por_formato = []
    for fmt, filas in sorted(por_fmt.items()):
        cantidad = min(len(filas), args.moderna) if fmt == "moderna" else len(filas)
        resumen_por_formato.append(f"{fmt}={cantidad}")
    print(f"A: {na}  " + "  ".join(resumen_por_formato))
    print(f"B: {nb}")
    print(f"-> {OUT}/  , muestra.csv , labels_plantilla.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
