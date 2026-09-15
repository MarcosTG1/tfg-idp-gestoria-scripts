# Scripts de reproducibilidad del TFG

En este repositorio dejo los scripts en Python que usé para la parte
cuantitativa de mi Trabajo de Fin de Grado, *Procesamiento Inteligente de
Documentos Aplicado a la Automatización de una Gestoría Administrativa de
Tráfico* (Grado en Ciencia de Datos, ETSE-UV). Corresponden al Capítulo 4
de la memoria (Metodología de evaluación y aprendizaje automático) y al
Apéndice A, donde están explicados con más detalle y están listados en la
Tabla A.2.

No subo aquí el conjunto de datos de evaluación, porque contiene
documentos reales de clientes de la gestoría (matrícula, nombre,
domicilio, número de bastidor) y no se puede redistribuir. Si el tutor o
el tribunal quieren consultar el código junto con la ground truth
congelada, sin los documentos originales, se lo puedo pasar aparte.

## En qué orden se ejecutan

1. Construcción y congelación del conjunto de evaluación:
   `extraer_permiso_circulacion.py`, `muestrear.py`, `excluir_muestras.py`,
   `congelar_dataset.py`, `amend_labels_v41.py`, `manifest_dataset.py`,
   `aplicar_labels.py`.
2. Reconocimiento óptico: `ocr_mistral.py`, `ocr_bench.py`,
   `extraer_offline.py`, `rasgos_pdf.py`.
3. Métricas de extracción y comparativa de OCR (apartados 4.2 y 4.3):
   `metricas_42.py`, `metricas_43.py`.
4. Asignación de expediente (apartados 4.4 y 4.5):
   `asignacion_heuristica_44.py`, `asignacion_online_44.py`,
   `features_45.py`, `modelo_45.py`.
5. Figuras del capítulo: `figura_bench_ocr.py`, `figura_confusion_42.py`,
   `figura_heuristica_44.py`, `figura_modelo_45.py`,
   `figura_pipeline_46.py`.

## Entorno

Usé Python 3.12 y scikit-learn 1.9 para la regresión logística y el
árbol. El reconocimiento óptico se hace con el modelo `mistral-ocr-latest`
de Mistral AI a través de su API; la clave se lee de la variable de
entorno `MISTRAL_API_KEY`, nunca se escribe en un fichero. Para la
comparativa de motores de código abierto usé Tesseract 5.5.3, PaddleOCR
2.7.3 y docTR 1.1.0, cada uno en su propio entorno virtual porque sus
dependencias no convivían bien.
