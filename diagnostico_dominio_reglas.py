"""
Módulo de Diagnóstico de Dominio Temático — Sistema Experto Basado en Reglas.

Reemplaza al antiguo "Modelo B" (RandomForestClassifier). El Modelo B original
entrenaba un clasificador para predecir 'dominio_tema' usando exactamente las
mismas variables (tasa_exito, atraso_prom_dias, intentos_prom_tema) con las que
se construía la propia etiqueta objetivo: fuga de datos directa, sin valor
predictivo real (accuracy ~100% ficticio).

Este módulo formaliza esa lógica como lo que realmente es: un sistema experto
determinista, no un modelo entrenado. No hay entrenamiento, no hay .pkl, no hay
train/test split — porque no hay nada que "aprender": el diagnóstico es una
función directa y transparente del comportamiento agregado del estudiante en
cada tema.

Justificación metodológica (para IV.6 / bases teóricas de la tesis):
Los sistemas expertos basados en reglas son un componente clásico y legítimo
dentro de arquitecturas de Sistemas Tutores Inteligentes híbridos (ver II.3
Bases teóricas), especialmente para módulos de diagnóstico donde se requiere
transparencia y trazabilidad total de la decisión ante el usuario/asesor
pedagógico — algo que un modelo de caja negra no ofrece. Los umbrales usados
aquí (tasa de éxito, atraso promedio, intentos promedio) están fundamentados
en los mismos criterios de rendimiento académico ya utilizados por OULAD para
definir 'final_result' (aprobación >= 40%, penalización por reintentos y
demoras), manteniendo consistencia con el resto del sistema.
"""

UMBRAL_MIN_INTERACCIONES = 2

UMBRAL_DEBILIDAD_TASA_EXITO = 0.40
UMBRAL_DEBILIDAD_ATRASO_DIAS = 2
UMBRAL_DEBILIDAD_INTENTOS = 5

UMBRAL_FORTALEZA_TASA_EXITO = 0.75
UMBRAL_FORTALEZA_ATRASO_DIAS = 0
UMBRAL_FORTALEZA_INTENTOS = 2


def diagnosticar_dominio_tema(tasa_exito, atraso_prom_dias, intentos_prom_tema, n_interacciones):
    """
    Determina el nivel de dominio del estudiante en un tema específico
    a partir de sus métricas de comportamiento agregadas en dicho tema.

    Parámetros
    ----------
    tasa_exito : float          Proporción de ejercicios resueltos con éxito en el tema (0-1).
    atraso_prom_dias : float    Promedio de días de atraso en las entregas del tema.
    intentos_prom_tema : float  Promedio de intentos por ejercicio en el tema.
    n_interacciones : int       Número de interacciones registradas en el tema.

    Retorna
    -------
    str : etiqueta de diagnóstico ('Fortaleza', 'Debilidad', 'Neutro',
          o 'Neutro - Datos Insuficientes')
    """
    if n_interacciones < UMBRAL_MIN_INTERACCIONES:
        return "Neutro - Datos Insuficientes"

    if (tasa_exito <= UMBRAL_DEBILIDAD_TASA_EXITO
            or atraso_prom_dias > UMBRAL_DEBILIDAD_ATRASO_DIAS
            or intentos_prom_tema >= UMBRAL_DEBILIDAD_INTENTOS):
        return "Debilidad"

    if (tasa_exito >= UMBRAL_FORTALEZA_TASA_EXITO
            and atraso_prom_dias <= UMBRAL_FORTALEZA_ATRASO_DIAS
            and intentos_prom_tema <= UMBRAL_FORTALEZA_INTENTOS):
        return "Fortaleza"

    return "Neutro"


def diagnosticar_dataframe(df_agg):
    """
    Aplica el diagnóstico a un DataFrame agregado por (id_estudiante, categoria_macro)
    con las columnas: tasa_exito, atraso_prom_dias, intentos_prom_tema, n_interacciones.
    Devuelve el mismo DataFrame con la columna 'dominio_tema' añadida.
    """
    df_agg = df_agg.copy()
    df_agg['dominio_tema'] = df_agg.apply(
        lambda row: diagnosticar_dominio_tema(
            row['tasa_exito'], row['atraso_prom_dias'],
            row['intentos_prom_tema'], row['n_interacciones']
        ),
        axis=1
    )
    return df_agg
