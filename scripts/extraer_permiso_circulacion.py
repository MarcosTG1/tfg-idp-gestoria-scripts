#!/usr/bin/env python3
"""De la descarga bruta de carpetas de expediente en
data/raw/dataset_eval/A_a_expedientar/<mes>/<expediente>/ extrae el
**permiso de circulacion definitivo** de cada expediente y lo copia, limpio y
renombrado, a data/raw/dataset_eval/A_permisos/.

En estos expedientes el permiso definitivo no tiene un nombre unico: el personal
lo guarda como "PC DEF", "PC D", "PC", "PC Y FT DEF", "PC PLACA",
"PERMISO CIRCULACION ...", etc. Aqui se prueban esos patrones por orden de
prioridad. Lo que no encaja o es ambiguo se marca en _extraccion.csv para
revisarlo a mano; no se inventa nada.

Uso:
    python scripts/extraer_permiso_circulacion.py
"""
import csv
import re
import shutil
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
ORIGEN = BASE / "A_a_expedientar"
DESTINO = BASE / "A_permisos"
CSV_SALIDA = DESTINO / "_extraccion.csv"

# patrones sobre el nombre sin extension, en minusculas y con espacios
# colapsados. Orden = prioridad (el primero que encaje gana).
PATRONES = [
    r"^pc def$",
    r"^pc d$",
    r"^pc$",
    r"^pc de$",
    r"^pc deef$",
    r"^pcdef$",
    r"^pc placa$",
    r"^pc placas$",
    r"^pc placa[_ ]merged.*$",
    r"^pc y ft def$",
    r"^pc y ft d$",
    r"^pc y ftd$",
    r"^pcn y ft def$",
    r"^pc y ft$",
    r"^permiso de circulacion.*$",
    r"^permiso circulacion.*$",
    r"^pc .*$",       # pc dup, pc pn publico, pc a, pc x...
    r"^pc[0-9x]$",    # pc2, pcx
]
PATRONES_C = [re.compile(p) for p in PATRONES]

TOKEN_MATRICULA = re.compile(r"^([A-Za-z]{0,2}[0-9]{3,4}[A-Za-z]{0,3}|[A-Za-z]{1,2}[0-9]{4,6})$")


def norm(stem):
    return re.sub(r"\s+", " ", stem.strip().lower())


def matricula_de(nombre_carpeta):
    primer_token = nombre_carpeta.strip().split(" ")[0].upper()
    return primer_token if TOKEN_MATRICULA.match(primer_token) else ""


def slug(texto):
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")


def elegir(pdfs):
    """Devuelve (fichero elegido, patron, todos los candidatos que encajan)."""
    candidatos = []
    for pdf in pdfs:
        nombre_normalizado = norm(pdf.stem)
        for indice_patron, patron_compilado in enumerate(PATRONES_C):
            if patron_compilado.match(nombre_normalizado):
                candidatos.append((indice_patron, pdf))
                break
    if not candidatos:
        return None, "", []
    candidatos.sort(key=lambda par: (par[0], par[1].name))
    mejor_prioridad = candidatos[0][0]
    empatados = [pdf for prioridad, pdf in candidatos if prioridad == mejor_prioridad]
    nombres = [pdf.name for _, pdf in candidatos]
    return empatados[0], PATRONES[mejor_prioridad], nombres if len(candidatos) > 1 else []


def main():
    if not ORIGEN.exists():
        print(f"No existe {ORIGEN}", file=sys.stderr)
        return 1
    DESTINO.mkdir(parents=True, exist_ok=True)

    filas = []
    n_ok = n_sin = n_multi = 0
    for exp in sorted(p for p in ORIGEN.glob("*/*") if p.is_dir()):
        mes = exp.parent.name
        pdfs = [p for p in exp.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
        matricula = matricula_de(exp.name)
        elegido, patron, candidatos = elegir(pdfs)

        if elegido is None:
            estado = "revisar_sin_pc"
            n_sin += 1
            destino_rel = ""
        else:
            estado = "ok"
            if candidatos:
                estado = "revisar_multiple"
                n_multi += 1
            else:
                n_ok += 1
            etiqueta = matricula or slug(exp.name)[:20] or "sinmatricula"
            destino = DESTINO / f"{mes}__{etiqueta}__{slug(elegido.stem)}.pdf"
            sufijo = 2
            while destino.exists():
                destino = DESTINO / f"{mes}__{etiqueta}__{slug(elegido.stem)}-{sufijo}.pdf"
                sufijo += 1
            shutil.copy2(elegido, destino)
            destino_rel = destino.name

        filas.append(
            {
                "mes": mes,
                "carpeta_expediente": exp.name,
                "matricula_token": matricula,
                "estado": estado,
                "fichero_elegido": elegido.name if elegido else "",
                "patron": patron,
                "n_pdf_carpeta": len(pdfs),
                "candidatos_pc": " | ".join(candidatos),
                "fichero_destino": destino_rel,
            }
        )

    with CSV_SALIDA.open("w", newline="", encoding="utf-8") as fichero_salida:
        escritor = csv.DictWriter(fichero_salida, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)

    print(f"expedientes procesados : {len(filas)}")
    print(f"  permiso extraido (ok): {n_ok}")
    print(f"  varios PC, revisar   : {n_multi}")
    print(f"  sin PC, revisar      : {n_sin}")
    print(f"-> PDF en {DESTINO}")
    print(f"-> detalle en {CSV_SALIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
