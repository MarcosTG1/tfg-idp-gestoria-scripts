#!/usr/bin/env python3
"""Reimplementacion offline de la extraccion de matricula del flujo de archivo
(nodo "Leer Matricula") y del emparejamiento de expediente (nodos "Filtrar
Coincidencia Exacta" y "Comprobar PCDEF Existente"), para evaluarla en el
Capitulo 4 sin tocar produccion.

Entrada:  data/raw/dataset_eval/ocr/mistral/<id>.json   (salida de Mistral OCR)
          data/raw/dataset_eval/muestra.csv             (lista de la muestra)
          data/raw/dataset_eval/A_a_expedientar/         (arbol de expedientes)
Salida:   data/raw/dataset_eval/prediccion_42.csv

Notas de fidelidad:
- El regex, el juego de letras, la lista de provincias y el orden de prueba
  (temporal antes que provincial) son los del nodo en produccion.
- La comprobacion de "PCDEF ya existe" NO se aplica: cada permiso de la muestra
  se tomo de su propia carpeta, asi que por construccion siempre existiria uno.
  FALLO_TECNICO tampoco es evaluable offline. Ambas quedan fuera de la matriz.
"""
import csv
import io
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
OCR = BASE / "ocr" / "mistral"
TREE = BASE / "A_a_expedientar"
SALIDA = BASE / "prediccion_42.csv"

LETRAS = "BCDFGHJKLMNPRSTVWXYZ"
PROVINCIAS = ["AB","AL","AV","BA","BI","BU","CA","CC","CE","CO","CR","CS","CU","GC","GE","GI","GR","GU","HU","LE","LO","LU","MA","ML","MU","NA","OR","OU","PM","PO","SA","SE","SG","SO","SS","TE","TF","TO","VA","VI","ZA","A","B","C","H","J","L","M","O","P","S","T","V","Z"]

cuerpoModerna = r"(\d{4})\s?-?\s?([" + LETRAS + r"]{3})"
cuerpoTemporal = r"([PS])\s?-?\s?(\d{4})\s?-?\s?([" + LETRAS + r"]{3})"
cuerpoEspecial = r"([CREH])\s?-?\s?(\d{4})\s?-?\s?([" + LETRAS + r"]{3})"  # serie especial R/E/H/C (hotfix 2026-09-07)
cuerpoAntigua = "(" + "|".join(PROVINCIAS) + r")\s?-?\s?(\d{4})\s?-?\s?([A-Z]{1,2})"
# Variante para matriculas provinciales de moto y ciclomotor: 4 a 6 digitos y las
# letras finales pasan a ser opcionales (hotfix 2026-09-07). Solo se usa en la
# capa 1 (celda del campo A, con anclas ^$): ahi el valor es la matricula y nada
# mas, de modo que relajar el patron no expone codigos del campo K ni fragmentos
# del bastidor, que solo aparecen en el barrido de la capa 2.
cuerpoAntiguaLarga = "(" + "|".join(PROVINCIAS) + r")\s?-?\s?(\d{4,6})\s?-?\s?([A-Z]{0,2})"

soloModerna = re.compile("^" + cuerpoModerna + "$")
soloTemporal = re.compile("^" + cuerpoTemporal + "$")
soloEspecial = re.compile("^" + cuerpoEspecial + "$")
soloAntigua = re.compile("^" + cuerpoAntigua + "$")
soloAntiguaLarga = re.compile("^" + cuerpoAntiguaLarga + "$")


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def leer_matricula(pages):
    texto = "\n".join(p.get("markdown", "") or "" for p in pages).upper()

    # CAPA 1: campo A de la tabla
    por_campo_a, tipo = "", ""
    for linea in texto.split("\n"):
        m = re.match(r"^\s*\|\s*A\s*\|\s*([^|]*?)\s*\|", linea)
        if not m:
            continue
        valor = m.group(1).strip()
        if soloTemporal.match(valor):
            por_campo_a, tipo = norm(valor), "temporal"
        elif soloEspecial.match(valor):
            por_campo_a, tipo = norm(valor), "especial"
        elif soloModerna.match(valor):
            por_campo_a, tipo = norm(valor), "moderna"
        elif soloAntigua.match(valor) or soloAntiguaLarga.match(valor):
            por_campo_a, tipo = norm(valor), "antigua"
        break

    # CAPA 2: barrido del texto completo
    vistos = []
    rangos = []

    def barrer(patron):
        for m in patron.finditer(texto):
            ini, fin = m.start(), m.end()
            if any(ini < b and fin > a for a, b in rangos):
                continue
            antes = re.split(r"[\n|]", texto[max(0, ini - 24):ini])[-1]
            despues = re.split(r"[\n|]", texto[fin:fin + 24])[0]
            if re.search(r"[A-Z0-9]{6,}$", re.sub(r"[^A-Z0-9]", "", antes)):
                continue
            if re.match(r"^[A-Z0-9]{6,}", re.sub(r"[^A-Z0-9]", "", despues)):
                continue
            rangos.append((ini, fin))
            cand = "".join(m.groups())
            if cand not in vistos:
                vistos.append(cand)

    barrer(re.compile(r"\b" + cuerpoEspecial + r"\b"))
    barrer(re.compile(r"\b" + cuerpoTemporal + r"\b"))
    barrer(re.compile(r"\b" + cuerpoModerna + r"\b"))
    barrer(re.compile(r"\b" + cuerpoAntigua + r"\b"))

    if por_campo_a:
        return {"matricula": por_campo_a, "candidatos": vistos, "leida_de": "campo A",
                "tipo": tipo, "ok": True, "motivo": ""}
    ok = len(vistos) == 1
    if len(vistos) == 0:
        motivo = "SIN_TEXTO" if len(texto.strip()) < 20 else "SIN_MATRICULA"
    elif len(vistos) > 1:
        motivo = "MATRICULA_AMBIGUA"
    else:
        motivo = ""
    return {"matricula": vistos[0] if ok else "", "candidatos": vistos,
            "leida_de": "barrido del texto" if ok else "", "tipo": "",
            "ok": ok, "motivo": motivo}


def indice_expedientes():
    """(nombre_normalizado, periodo AAAA-MM, ruta) por carpeta de expediente."""
    idx = []
    for exp in TREE.glob("*/*"):
        if not exp.is_dir():
            continue
        mes = exp.parent.name
        anio = "2026" if mes in {"01", "02", "03", "04", "05"} else "2025"
        idx.append((norm(exp.name), f"{anio}-{mes}", exp))
    return idx


def emparejar(matricula, idx):
    valida = bool(matricula) and 6 <= len(matricula) <= 8
    carpetas = [(n, per, p) for (n, per, p) in idx if valida and n.startswith(matricula)]
    carpetas.sort(key=lambda t: t[1], reverse=True)
    resuelto = desempatada = False
    ganadora = None
    if len(carpetas) == 1:
        resuelto, ganadora = True, carpetas[0]
    elif len(carpetas) > 1:
        if carpetas[0][1] and carpetas[0][1] != carpetas[1][1]:
            resuelto = desempatada = True
            ganadora = carpetas[0]
    return {"n_carpetas": len(carpetas), "resuelto": resuelto,
            "desempatada": desempatada,
            "ganadora": ganadora[2].parent.name + "/" + ganadora[2].name if ganadora else ""}


def categoria(lectura, emparejamiento):
    if lectura["motivo"]:
        return {"SIN_TEXTO": "sin_texto", "SIN_MATRICULA": "sin_matricula",
                "MATRICULA_AMBIGUA": "matricula_ambigua"}[lectura["motivo"]]
    if emparejamiento["n_carpetas"] == 0:
        return "expediente_no_encontrado"
    if not emparejamiento["resuelto"]:
        return "expediente_duplicado"
    if emparejamiento["desempatada"]:
        return "aviso_multiexpediente"
    return "archivado"


def main():
    muestra = list(csv.DictReader((BASE / "muestra.csv").read_text(encoding="utf-8-sig").splitlines()))
    idx = indice_expedientes()
    filas = []
    faltan = 0
    for r in muestra:
        ruta_json = OCR / (r["id"] + ".json")
        if not ruta_json.exists():
            faltan += 1
            continue
        pages = json.loads(ruta_json.read_text(encoding="utf-8")).get("pages", [])
        lectura = leer_matricula(pages)
        emparejamiento = emparejar(lectura["matricula"], idx) if r["poblacion"] == "A" else {
            "n_carpetas": "", "resuelto": "", "desempatada": "", "ganadora": ""}
        cat = categoria(lectura, emparejamiento) if r["poblacion"] == "A" else ""
        filas.append({
            "id": r["id"], "poblacion": r["poblacion"],
            "matricula_extraida": lectura["matricula"], "tipo": lectura["tipo"],
            "leida_de": lectura["leida_de"], "candidatos": " ".join(lectura["candidatos"]),
            "n_paginas": len(pages),
            "categoria_predicha": cat,
            "n_carpetas": emparejamiento["n_carpetas"], "desempatada": emparejamiento["desempatada"],
            "ganadora": emparejamiento["ganadora"],
        })
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(filas[0].keys()))
    w.writeheader()
    w.writerows(filas)
    SALIDA.write_text(buf.getvalue(), encoding="utf-8")
    print(f"{len(filas)} predicciones -> {SALIDA}  (sin OCR: {faltan})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
