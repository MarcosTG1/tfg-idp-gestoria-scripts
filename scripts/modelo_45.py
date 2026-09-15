#!/usr/bin/env python3
"""Apartado 4.5: modelo entrenado para elegir expediente en los 29 permisos de
matricula ambigua, comparado con las reglas del apartado 4.4.

Los pares (permiso, carpeta) de data/raw/dataset_eval/pares_45.csv se puntuan con
un clasificador; para cada permiso se elige la carpeta de mayor probabilidad. Se
usa validacion cruzada dejando fuera un permiso en cada iteracion (29 pliegues),
de modo que ningun par del permiso de prueba entra en el entrenamiento.

  - Principal: regresion logistica (rasgos estandarizados).
  - Apunte:   arbol de decision de profundidad 2.
  - Variante con abstencion: si el margen entre las dos mejores probabilidades es
    menor que EPS, el permiso queda "sin resolver" (comparable con las reglas).

Salida: docs/notes/aut_2/resultados_45.md (+ .json)
"""
import csv
import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

BASE = Path(__file__).resolve().parent.parent / "data" / "raw" / "dataset_eval"
PARES = BASE / "pares_45.csv"
RES44 = Path(__file__).resolve().parent.parent / "docs" / "notes" / "aut_2" / "resultados_44.json"
OUT = Path(__file__).resolve().parent.parent / "docs" / "notes" / "aut_2" / "resultados_45.md"
EPS = 0.15
ARCHIVADOS_DIRECTOS = 127  # permisos de la poblacion A ya archivados sin ambiguedad (apartado 4.2)
POB_A = 158

RASGOS = [
    "mes_coincide_i1", "es_mas_reciente_ct", "es_mas_antigua_ct", "dias_i1_vs_creacion",
    "rango_dias_candidatas", "i1_literal_en_carpeta", "bastidor_en_carpeta",
    "titular_en_carpeta", "n_docs", "tiene_pc_def", "hay_otra_mismo_mes", "n_candidatas",
]


def cargar():
    filas = list(csv.DictReader(PARES.read_text(encoding="utf-8").splitlines()))
    ids = sorted({f["id"] for f in filas})
    return filas, ids


def evalua(filas, ids, modelo_fn, estandariza, rasgos=None):
    """LOO por permiso. El acierto se mide a nivel de carpeta (columna `carpeta`,
    verdad de referencia v4.1). Devuelve (detalle, coef_medio)."""
    rasgos = list(rasgos) if rasgos is not None else RASGOS
    detalle = []
    coefs = []
    for held in ids:
        tr = [f for f in filas if f["id"] != held]
        te = [f for f in filas if f["id"] == held]
        Xtr = np.array([[float(f[r]) for r in rasgos] for f in tr])
        ytr = np.array([int(f["es_correcta"]) for f in tr])
        Xte = np.array([[float(f[r]) for r in rasgos] for f in te])
        var = Xtr.std(axis=0) > 1e-9  # columnas no constantes en el train
        Xtr_v, Xte_v = Xtr[:, var], Xte[:, var]
        if estandariza:
            sc = StandardScaler().fit(Xtr_v)
            Xtr_v, Xte_v = sc.transform(Xtr_v), sc.transform(Xte_v)
        clf = modelo_fn().fit(Xtr_v, ytr)
        prob = clf.predict_proba(Xte_v)[:, 1]
        if hasattr(clf, "coef_"):
            c = np.zeros(len(rasgos))
            c[np.where(var)[0]] = clf.coef_[0]
            coefs.append(c)
        orden = np.argsort(prob)[::-1]
        top = te[orden[0]]
        margen = float(prob[orden[0]] - prob[orden[1]]) if len(prob) > 1 else 1.0
        gt_carp = next(f["carpeta"] for f in te if f["es_correcta"] == "1")
        detalle.append({"id": held, "elegida": top["carpeta"], "gt": gt_carp,
                        "acierto": top["carpeta"] == gt_carp, "margen": round(margen, 3)})
    return detalle, (np.mean(coefs, axis=0) if coefs else None)


def ablacion(filas, ids):
    """Cuantos aciertos conserva la regresion logistica al quitar rasgos.
    Devuelve una lista de (etiqueta, rasgos_usados, aciertos)."""
    construccion = ["i1_literal_en_carpeta", "titular_en_carpeta", "tiene_pc_def"]
    variantes = [
        ("modelo completo (12 rasgos)", RASGOS),
        ("sin tiene_pc_def", [r for r in RASGOS if r != "tiene_pc_def"]),
        ("sin los 3 rasgos favorecidos por construccion",
         [r for r in RASGOS if r not in construccion]),
        ("solo mes_coincide_i1", ["mes_coincide_i1"]),
    ]
    lr = lambda: LogisticRegression(max_iter=2000, C=1.0)
    out = []
    for etq, rs in variantes:
        det, _ = evalua(filas, ids, lr, estandariza=True, rasgos=rs)
        out.append((etq, rs, sum(d["acierto"] for d in det)))
    return out


def cuenta(detalle, con_abstencion):
    """(bien, sin_resolver, mal) que suman len(detalle)."""
    bien = sr = mal = 0
    for d in detalle:
        if con_abstencion and d["margen"] < EPS:
            sr += 1
        elif d["acierto"]:
            bien += 1
        else:
            mal += 1
    return bien, sr, mal


def main():
    filas, ids = cargar()
    n = len(ids)

    lr = lambda: LogisticRegression(max_iter=2000, C=1.0)
    dt = lambda: DecisionTreeClassifier(max_depth=2, random_state=0)

    det_lr, coef_lr = evalua(filas, ids, lr, estandariza=True)
    det_dt, _ = evalua(filas, ids, dt, estandariza=False)
    lr_se = cuenta(det_lr, con_abstencion=False)   # (bien, 0, mal)
    lr_ab = cuenta(det_lr, con_abstencion=True)     # (bien, sr, mal)
    dt_se = cuenta(det_dt, con_abstencion=False)
    ok_lr = lr_se[0]

    # arbol final sobre todos los pares, para enseñar sus cortes
    X = np.array([[float(f[r]) for r in RASGOS] for f in filas])
    y = np.array([int(f["es_correcta"]) for f in filas])
    arbol_full = DecisionTreeClassifier(max_depth=2, random_state=0).fit(X, y)
    reglas_arbol = export_text(arbol_full, feature_names=list(RASGOS))

    r44 = json.loads(RES44.read_text())
    base = {k: (r44["aciertos"][k], r44["sin_resolver"][k], r44["n"] - r44["aciertos"][k] - r44["sin_resolver"][k])
            for k in ("r1", "r2", "r3")}

    coef_orden = sorted(zip(RASGOS, coef_lr), key=lambda t: -abs(t[1]))

    abl = ablacion(filas, ids)
    r1_ok = base["r1"][0]

    e2e = ARCHIVADOS_DIRECTOS + ok_lr
    e2e_r1 = ARCHIVADOS_DIRECTOS + r1_ok

    lineas_salida = ["# Resultados 4.5 - Modelo entrenado de asignacion de expediente\n",
         f"Generado por `scripts/modelo_45.py`. {len(filas)} pares "
         f"(permiso, carpeta) de {n} permisos ambiguos. LOO por permiso.\n",
         "## Comparativa (aciertos / a revision / mal, sobre 29; base de produccion)\n",
         "| Metodo | Bien | A revision | Mal | Exactitud |",
         "|---|---|---|---|---|",
         f"| R1 mas reciente por createdTime (flujo) | {base['r1'][0]} | {base['r1'][1]} | {base['r1'][2]} | {100*base['r1'][0]/n:.1f}\\% |",
         f"| R2 R1 + anclaje por mes de la fecha I.1 | {base['r2'][0]} | {base['r2'][1]} | {base['r2'][2]} | {100*base['r2'][0]/n:.1f}\\% |",
         f"| R3 R2 + confirmacion por contenido | {base['r3'][0]} | {base['r3'][1]} | {base['r3'][2]} | {100*base['r3'][0]/n:.1f}\\% |",
         f"| Regresion logistica, siempre elige | {lr_se[0]} | {lr_se[1]} | {lr_se[2]} | {100*lr_se[0]/n:.1f}\\% |",
         f"| Regresion logistica, con abstencion (margen<{EPS}) | {lr_ab[0]} | {lr_ab[1]} | {lr_ab[2]} | {100*lr_ab[0]/n:.1f}\\% |",
         f"| Arbol de decision, profundidad 2 | {dt_se[0]} | {dt_se[1]} | {dt_se[2]} | {100*dt_se[0]/n:.1f}\\% |",
         "",
         "Nota: la variante con abstencion no cambia los aciertos; reetiqueta como "
         "sin resolver los casos en que las dos mejores probabilidades quedan cerca.",
         "",
         "## Coeficientes de la regresion logistica (media de los 29 pliegues, rasgos estandarizados)\n",
         "| Rasgo | Coef. |",
         "|---|---|"]
    for r, c in coef_orden:
        lineas_salida.append(f"| {r} | {c:+.2f} |")
    lineas_salida += ["",
          "## Cortes del arbol de profundidad 2 (ajustado a todos los pares)\n",
          "```", reglas_arbol.rstrip(), "```", "",
          "## Analisis de sensibilidad (aciertos de la regresion logistica, sobre 29)\n",
          "| Variante | Rasgos | Aciertos |",
          "|---|---|---|"]
    for etq, rs, ok in abl:
        lineas_salida.append(f"| {etq} | {len(rs)} | {ok}/{n} |")
    lineas_salida += ["",
          f"R1, la regla del flujo, acierta {r1_ok}/{n} sin ningun archivo mal. "
          f"El modelo no la supera de forma robusta: su margen se apoya en rasgos "
          f"favorecidos por la construccion del conjunto.",
          "",
          "## Casos que la regresion logistica no coloca bien\n"]
    for d in det_lr:
        if not d["acierto"]:
            lineas_salida.append(f"- {d['id']}  elegida {d['elegida']}  esperado {d['gt']}  (margen {d['margen']})")
    lineas_salida += ["",
          "## Archivo de la poblacion A de extremo a extremo\n",
          f"En el apartado 4.2, la cadena archiva bien {ARCHIVADOS_DIRECTOS} de los {POB_A} "
          f"permisos de la poblacion A; los {n} que fallan son los ambiguos de este apartado "
          f"mas 2 de nombre de carpeta erroneo. Resolviendo los ambiguos con la regla del "
          f"flujo R1 ({r1_ok}/{n}) el archivo correcto pasa de "
          f"{ARCHIVADOS_DIRECTOS}/{POB_A} ({100*ARCHIVADOS_DIRECTOS/POB_A:.1f}\\%) a "
          f"{e2e_r1}/{POB_A} ({100*e2e_r1/POB_A:.1f}\\%). La regresion logistica "
          f"({ok_lr}/{n}) no mejora esa cifra de forma fiable.",
          ""]
    OUT.write_text("\n".join(lineas_salida), encoding="utf-8")
    OUT.with_suffix(".json").write_text(json.dumps({
        "n": n, "pares": len(filas),
        "lr": {"bien": lr_se[0], "mal": lr_se[2],
               "abstencion": {"bien": lr_ab[0], "sin_resolver": lr_ab[1], "mal": lr_ab[2]}},
        "arbol": {"bien": dt_se[0], "sin_resolver": dt_se[1], "mal": dt_se[2]},
        "reglas": {k: {"ok": v[0], "sin_resolver": v[1], "mal": v[2]} for k, v in base.items()},
        "coeficientes": {r: round(float(c), 4) for r, c in coef_orden},
        "ablacion": [{"variante": etq, "n_rasgos": len(rs), "aciertos": ok} for etq, rs, ok in abl],
        "e2e": {"antes": ARCHIVADOS_DIRECTOS, "despues": e2e, "despues_r1": e2e_r1,
                "r1_ok": r1_ok, "total": POB_A},
        "detalle_lr": det_lr,
    }, indent=2), encoding="utf-8")
    print("\n".join(lineas_salida))
    print("->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
