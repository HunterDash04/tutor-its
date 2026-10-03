# Pipeline de datos y modelos

Esta carpeta reproduce, desde los datos públicos, los dos modelos del sistema y los archivos que usa la app (`motor_recomendacion.pkl` y `calibracion_diagnostico.json`).

**Todos los comandos se ejecutan desde la raíz del repositorio.**

## Requisitos
```
py -m pip install -r pipeline/requirements-pipeline.txt
```

## Datos de entrada (no se incluyen en el repositorio)
| Dataset | Cómo obtenerlo | Dónde colocarlo |
|---|---|---|
| OULAD | Descargar del sitio oficial de la Open University (Kuzilek et al., 2017) | `datasets/` (archivos `studentInfo.csv`, `studentRegistration.csv`, `courses.csv`, `assessments.csv`, `studentAssessment.csv`, `vle.csv`, `studentVle.csv`) |
| Codeforces | `py pipeline/descargar_codeforces.py` (API pública, cerca de 1 hora; se puede reanudar si se corta) | Se genera solo en `datasets/codeforces/` |

## Orden de ejecución
| # | Comando | Resultado | Tiempo aprox. |
|---|---|---|---|
| 1 | `py pipeline/agregar_vle.py` | `vle_features_agregadas.csv` | 2 min |
| 2 | `py pipeline/construir_dataset_estudiante.py 0.5` | `dataset_estudiante_corte50.csv` (y opcionalmente `0.25` y `0.75`) | 1 min |
| 3 | `py pipeline/entrenar_modelo_a.py` | `resultados_modelo_a/` y `modelo_diagnostico_final.pkl` | 10 min |
| 4 | `py pipeline/descargar_codeforces.py` | `datasets/codeforces/` | 1 h |
| 5 | `py pipeline/entrenar_recomendador.py` | `resultados_recomendador/`, `motor_recomendacion.pkl` y `calibracion_diagnostico.json` | 5 min |

Los pasos 3 y 5 son independientes entre sí. Para actualizar la app basta con el paso 5: sube el `.pkl` y el `.json` nuevos al repositorio y Streamlit Cloud se redespliega solo.

## Reproducibilidad
- **Semillas:** todas fijas (`SEMILLA = 42`).
- **Validación:** siempre agrupada por estudiante o usuario, para que nadie esté a la vez en entrenamiento y en prueba.
- **Sin mirar el futuro:** las variables de cada intento se calculan solo con información anterior a ese intento.
- **Versiones:** las librerías están fijadas en `requirements-pipeline.txt`. El `.pkl` se carga en la app con la misma versión de scikit-learn (1.9.1).

La descripción de cada variable está en [`DICCIONARIO_DATOS.md`](DICCIONARIO_DATOS.md).
