#!/usr/bin/env python3
"""Banco de pruebas de motores de OCR de codigo abierto para el apartado 4.3.

Sobre los mismos 231 permisos del conjunto v4, rasteriza cada PDF a PNG de
300 dpi y pasa el motor indicado, guardando el texto reconocido y el tiempo de
proceso. No toca produccion ni el flujo. La salida de Mistral OCR ya esta en
data/raw/dataset_eval/ocr/mistral/ y no se vuelve a pedir.

Entradas : data/raw/dataset_eval/muestra.csv
           data/raw/dataset_eval/muestra/{A,B}/<fichero>.pdf
Salidas  : data/raw/dataset_eval/img/<id>/p<n>.png        (cache de rasterizado)
           data/raw/dataset_eval/ocr/<motor>/<id>.txt      (texto reconocido)
           data/raw/dataset_eval/ocr/<motor>/timing.csv    (id, segundos, paginas)

Uso:
    python scripts/ocr_bench.py rasterize
    python scripts/ocr_bench.py tesseract
    python scripts/ocr_bench.py paddleocr
    python scripts/ocr_bench.py doctr

Cada motor se ejecuta en su propio proceso para no cargar dos frameworks a la
vez. Es idempotente: si <id>.txt ya existe, no lo rehace.
"""
import csv
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
MUESTRA = BASE / "muestra.csv"
PDFS = BASE / "muestra"
IMG = BASE / "img"
OCR = BASE / "ocr"
DPI = 300


def ids():
    out = []
    for r in csv.DictReader(MUESTRA.read_text(encoding="utf-8-sig").splitlines()):
        pdf = PDFS / r["poblacion"] / r["fichero"]
        out.append((r["id"], r["poblacion"], pdf))
    return out


def rasteriza(idn, pdf):
    """Devuelve las paginas PNG de un permiso, generandolas si faltan."""
    dst = IMG / idn
    paginas = sorted(dst.glob("p*.png"))
    if paginas:
        return paginas
    dst.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(DPI), str(pdf), str(dst / "p")],
        check=True, capture_output=True,
    )
    # pdftoppm escribe p-1.png, p-2.png...; se renombra a p1.png para orden estable
    for f in sorted(dst.glob("p-*.png")):
        n = int(f.stem.split("-")[1])
        f.rename(dst / f"p{n}.png")
    return sorted(dst.glob("p*.png"))


# --------------------------------------------------------------------------- #
#  Motores                                                                    #
# --------------------------------------------------------------------------- #
def motor_tesseract():
    import pytesseract
    from PIL import Image

    def run(paginas):
        # psm 3: segmentacion de pagina automatica, el modo por defecto de
        # Tesseract. Se probaron tambien psm 6 y psm 4 sobre el conjunto completo
        # y dan una exactitud de matricula igual o peor, asi que se deja el
        # comportamiento por defecto.
        trozos = []
        for p in paginas:
            trozos.append(pytesseract.image_to_string(
                Image.open(p), lang="spa+eng", config="--oem 1 --psm 3"))
        return "\n\n".join(trozos)

    return run


def motor_paddleocr():
    from paddleocr import PaddleOCR

    ocr = PaddleOCR(use_angle_cls=True, lang="es", show_log=False, use_gpu=False)

    def run(paginas):
        trozos = []
        for p in paginas:
            res = ocr.ocr(str(p), cls=True)
            lineas = []
            for bloque in res or []:
                for item in bloque or []:
                    lineas.append(item[1][0])
            trozos.append("\n".join(lineas))
        return "\n\n".join(trozos)

    return run


def motor_doctr():
    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor

    modelo = ocr_predictor(pretrained=True)

    def run(paginas):
        doc = DocumentFile.from_images([str(p) for p in paginas])
        return modelo(doc).render()

    return run


MOTORES = {
    "tesseract": motor_tesseract,
    "paddleocr": motor_paddleocr,
    "doctr": motor_doctr,
}


def corre_motor(nombre):
    run = MOTORES[nombre]()
    salida = OCR / nombre
    salida.mkdir(parents=True, exist_ok=True)
    tfile = salida / "timing.csv"
    timing = []
    if tfile.exists():
        timing = list(csv.reader(tfile.read_text().splitlines()))[1:]
    hechos = {row[0] for row in timing}

    lista = ids()
    for k, (idn, _pob, pdf) in enumerate(lista, 1):
        destino = salida / f"{idn}.txt"
        if destino.exists() and idn in hechos:
            continue
        paginas = rasteriza(idn, pdf)
        t0 = time.perf_counter()
        try:
            texto = run(paginas)
        except Exception as e:
            texto = ""
            print(f"  [{nombre}] ERROR en {idn}: {e}")
        dt = time.perf_counter() - t0
        destino.write_text(texto, encoding="utf-8")
        timing = [row for row in timing if row[0] != idn]
        timing.append([idn, f"{dt:.3f}", str(len(paginas))])
        if k % 10 == 0 or k == len(lista):
            print(f"  [{nombre}] {k}/{len(lista)}  ultimo {idn} {dt:.2f}s")
        with tfile.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "segundos", "paginas"])
            w.writerows(sorted(timing))
    print(f"[{nombre}] completado: {len(list(salida.glob('*.txt')))} ficheros")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    modo = sys.argv[1]
    if modo == "rasterize":
        lista = ids()
        for k, (idn, _p, pdf) in enumerate(lista, 1):
            n = len(rasteriza(idn, pdf))
            if k % 25 == 0 or k == len(lista):
                print(f"  rasterizadas {k}/{len(lista)}  ({idn}: {n} pag)")
        return 0
    if modo in MOTORES:
        return corre_motor(modo)
    print(f"modo desconocido: {modo}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
