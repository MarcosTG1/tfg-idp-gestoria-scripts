#!/usr/bin/env python3
"""Pasa los 231 permisos de data/raw/dataset_eval/muestra/{A,B}/ por Mistral OCR,
con la misma llamada que el nodo "OCR del Permiso" del flujo en produccion:

    POST https://api.mistral.ai/v1/ocr
    body: {model: "mistral-ocr-latest",
           document: {type: "document_url",
                      document_url: "data:application/pdf;base64," + <b64>}}

Guarda la respuesta completa (con pages[].markdown) en
data/raw/dataset_eval/ocr/mistral/<id>.json

La clave se lee de la variable de entorno MISTRAL_API_KEY. No se escribe en
ningun fichero.

Uso:
    export MISTRAL_API_KEY=...
    python3 scripts/ocr_mistral.py
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
MUESTRA = BASE / "muestra"
OUT = BASE / "ocr" / "mistral"
URL = "https://api.mistral.ai/v1/ocr"
MODEL = "mistral-ocr-latest"


def ocr_pdf(pdf, key):
    b64 = base64.b64encode(pdf.read_bytes()).decode("ascii")
    body = json.dumps({
        "model": MODEL,
        "document": {
            "type": "document_url",
            "document_url": "data:application/pdf;base64," + b64,
        },
    }).encode("utf-8")
    req = urllib.request.Request(
        URL, data=body, method="POST",
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not key:
        print("Falta MISTRAL_API_KEY en el entorno", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(MUESTRA.rglob("*.pdf"))
    hecho = fallo = salto = 0
    for i, pdf in enumerate(pdfs, 1):
        dst = OUT / (pdf.stem + ".json")
        if dst.exists() and dst.stat().st_size > 0:
            salto += 1
            continue
        for intento in range(1, 5):
            try:
                res = ocr_pdf(pdf, key)
                dst.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
                hecho += 1
                print(f"[{i}/{len(pdfs)}] {pdf.stem}  paginas={len(res.get('pages', []))}")
                break
            except urllib.error.HTTPError as e:
                cuerpo = e.read().decode("utf-8", "replace")[:200]
                print(f"[{i}/{len(pdfs)}] {pdf.stem}  HTTP {e.code} (intento {intento}): {cuerpo}", file=sys.stderr)
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(5 * intento)
                    continue
                fallo += 1
                break
            except Exception as e:
                print(f"[{i}/{len(pdfs)}] {pdf.stem}  error (intento {intento}): {e}", file=sys.stderr)
                time.sleep(3 * intento)
        else:
            fallo += 1
        time.sleep(0.4)

    print(f"\nOK {hecho}  saltados {salto}  fallidos {fallo}  -> {OUT}")
    return 1 if fallo else 0


if __name__ == "__main__":
    raise SystemExit(main())
