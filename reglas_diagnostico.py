"""
reglas_diagnostico.py — fuente única de verdad para los estados cognitivos del ITS.

Estados (3): definidos a partir de final_result de OULAD.
  - Riesgo - Reforzar Fundamentos      (Fail + Withdrawn)
  - Aprendizaje Normal - Mantener Ruta (Pass)
  - Dominio Alto - Ruta Avanzada       (Distinction)

Fail y Withdrawn se agrupan porque ambos requieren la misma intervención pedagógica
(remediación) y, a mitad de curso, el comportamiento observable no permite
distinguirlos de forma fiable (experimento de 4 clases: F1 de Withdrawn = 0.10).
"""
import numpy as np

ESTADO_RIESGO = 'Riesgo - Reforzar Fundamentos'
ESTADO_NORMAL = 'Aprendizaje Normal - Mantener Ruta'
ESTADO_DOMINIO = 'Dominio Alto - Ruta Avanzada'

MAPEO_ESTADO_COGNITIVO = {
    'Withdrawn': ESTADO_RIESGO,
    'Fail': ESTADO_RIESGO,
    'Pass': ESTADO_NORMAL,
    'Distinction': ESTADO_DOMINIO,
}


def etiquetar_estado_cognitivo(final_result):
    return MAPEO_ESTADO_COGNITIVO.get(final_result, ESTADO_NORMAL)


# ---------------------------------------------------------------------------
# GPA de referencia SOLO para poblar la base de datos del simulador (calibrar la
# dificultad inicial). NO se usa como variable del modelo predictivo: incluye un
# componente aleatorio y por eso fue retirado del Modelo A.
# ---------------------------------------------------------------------------
EDUC_SCORE = {
    'No Formal quals': 0,
    'Lower Than A Level': 1,
    'A Level or Equivalent': 2,
    'HE Qualification': 3,
    'Post Graduate Qualification': 4,
}


def calcular_gpa_historico(highest_education, num_of_prev_attempts, id_student):
    base = 10 + EDUC_SCORE.get(highest_education, 1) * 2.0
    penalizacion = num_of_prev_attempts * 0.8
    rng = np.random.RandomState(int(id_student) % (2**31))
    ruido = rng.uniform(-1.0, 1.0)
    gpa = base - penalizacion + ruido
    return round(min(max(gpa, 8.0), 20.0), 1)


# ---------------------------------------------------------------------------
# Diagnóstico para sesiones EN VIVO (simulador de consola).
# Sistema de reglas explícito, separado del Modelo A validado estadísticamente
# (el simulador no dispone del historial de clics y notas de medio curso que
# usa el modelo). Produce los mismos 3 estados.
# ---------------------------------------------------------------------------
UMBRAL_RIESGO_INTENTOS = 5
UMBRAL_RIESGO_ATRASO = 0
UMBRAL_RIESGO_TIEMPO = 450
UMBRAL_DOMINIO_TIEMPO = 150
UMBRAL_DOMINIO_INTENTOS = 2


def diagnosticar_estado_vivo(tiempo_segundos, n_intentos, exito_fallo, dias_atraso, porcentaje_progreso=None):
    if (exito_fallo == 0
            or n_intentos >= UMBRAL_RIESGO_INTENTOS
            or dias_atraso > UMBRAL_RIESGO_ATRASO
            or tiempo_segundos >= UMBRAL_RIESGO_TIEMPO):
        return ESTADO_RIESGO
    if (exito_fallo == 1
            and tiempo_segundos <= UMBRAL_DOMINIO_TIEMPO
            and n_intentos <= UMBRAL_DOMINIO_INTENTOS):
        return ESTADO_DOMINIO
    return ESTADO_NORMAL
