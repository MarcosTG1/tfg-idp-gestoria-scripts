#!/usr/bin/env python3
"""Congela el conjunto de evaluacion en una version inmutable.

Copia labels.csv, muestra.csv, excluidos.csv y un manifiesto de la carpeta
muestra/ (con hash sha1 de cada PDF) a data/raw/dataset_eval/<version>/, y
escribe un README con la fecha, los recuentos y la semilla.

Uso:
    python scripts/congelar_dataset.py v1
"""
import csv
import hashlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
MUESTRA = BASE / "muestra"
COPIAR = ["labels.csv", "muestra.csv", "excluidos.csv", "rasgos_pdf.csv"]


def sha1(ruta):
    hasher = hashlib.sha1()
    with ruta.open("rb") as fichero:
        for bloque in iter(lambda: fichero.read(65536), b""):
            hasher.update(bloque)
    return hasher.hexdigest()


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    dst = BASE / version
    if dst.exists():
        print(f"ya existe {dst}; borra la carpeta si quieres rehacer la version", file=sys.stderr)
        return 1
    dst.mkdir(parents=True)

    for nombre in COPIAR:
        src = BASE / nombre
        if src.exists():
            shutil.copy2(src, dst / nombre)

    # manifiesto de la muestra congelada
    filas = []
    for pdf in sorted(MUESTRA.rglob("*.pdf")):
        rel = pdf.relative_to(MUESTRA)
        filas.append({
            "id": pdf.stem,
            "poblacion": rel.parts[0],
            "fichero": str(rel),
            "bytes": pdf.stat().st_size,
            "sha1": sha1(pdf),
        })
    with (dst / "manifest_muestra.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "poblacion", "fichero", "bytes", "sha1"])
        w.writeheader()
        w.writerows(filas)

    na = sum(1 for f in filas if f["poblacion"] == "A")
    nb = sum(1 for f in filas if f["poblacion"] == "B")
    sello = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    checks = "\n".join(f"- {n}: sha1 {sha1(dst / n)}" for n in COPIAR if (dst / n).exists())
    readme = f"""# Conjunto de evaluacion - {version}

Congelado: {sello}

- Permisos: {len(filas)}  ({na} poblacion A, {nb} poblacion B)
- Semilla de muestreo: 20260907
- Ficheros de la muestra bajo `muestra/` (no versionados en git); su hash sha1
  esta en `manifest_muestra.csv`.

## Contenido de esta carpeta
{checks}
- manifest_muestra.csv: id, poblacion, fichero, bytes, sha1 de cada PDF

## Reglas
- Esta version NO se modifica. Todas las metricas del Capitulo 4 se calculan
  contra ella. Si se anaden o corrigen datos, se crea una version nueva.
- Verdad de referencia: `labels.csv`, transcrita y verificada a mano,
  permiso a permiso.

## Decision sobre anonimizacion
El autor ha decidido (2026-09-07) NO anonimizar los PDF del conjunto. Se
conservan integros. Antes de incluir cualquier pagina como figura en la
memoria o de compartir/depositar el conjunto, resolver con el tutor las
implicaciones de proteccion de datos.
"""
    (dst / "README.md").write_text(readme, encoding="utf-8")

    print(f"congelado en {dst}")
    print(f"  {len(filas)} PDF ({na} A + {nb} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
