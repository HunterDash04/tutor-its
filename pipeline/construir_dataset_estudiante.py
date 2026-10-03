"""
construir_dataset_estudiante.py

Construye el dataset del Modelo A (diagnóstico de estado cognitivo) con UNA FILA
POR ESTUDIANTE-CURSO, usando solo datos REALES de OULAD observados hasta un día de
corte (predicción temprana). Reemplaza a dataset_modeloA_features_reales.csv.

Por qué este diseño:
  - La etiqueta (final_result) describe al estudiante en todo el curso, así que la
    unidad de análisis debe ser el estudiante-curso, no cada entrega individual.
  - Solo se usa información disponible ANTES del día de corte -> no hay fuga
    temporal: el modelo predice el resultado final sin haberlo visto.
  - Se excluye a quien ya se retiró antes del corte (su resultado ya es conocido).
  - No hay variables sintéticas ni con ruido aleatorio (se elimina gpa_historico,
    que se generaba con números aleatorios; se usan las variables originales).

Uso (desde la raíz del repositorio, con datasets/ y vle_features_agregadas.csv):
    py pipeline/construir_dataset_estudiante.py            -> corte al 50% del curso
    py pipeline/construir_dataset_estudiante.py 0.25       -> corte al 25% del curso
Genera: dataset_estudiante_corte50.csv (o el % indicado)
"""
import sys
import numpy as np
import pandas as pd

DIR = 'datasets/'
RUTA_VLE = 'vle_features_agregadas.csv'

ORD_EDU = {'No Formal quals': 0, 'Lower Than A Level': 1, 'A Level or Equivalent': 2,
           'HE Qualification': 3, 'Post Graduate Qualification': 4}
ORD_EDAD = {'0-35': 0, '35-55': 1, '55<=': 2}
ORD_IMD = {'0-10%': 0, '10-20': 1, '10-20%': 1, '20-30%': 2, '30-40%': 3, '40-50%': 4,
           '50-60%': 5, '60-70%': 6, '70-80%': 7, '80-90%': 8, '90-100%': 9}
CLAVE = ['id_student', 'code_module', 'code_presentation']


def construir(fraccion_corte=0.5, dir_datos=DIR, ruta_vle=RUTA_VLE):
    si = pd.read_csv(dir_datos + 'studentInfo.csv')
    reg = pd.read_csv(dir_datos + 'studentRegistration.csv')
    cursos = pd.read_csv(dir_datos + 'courses.csv')
    asses = pd.read_csv(dir_datos + 'assessments.csv')
    sa = pd.read_csv(dir_datos + 'studentAssessment.csv')
    vle = pd.read_csv(ruta_vle)

    # ---------- base: estudiante-curso + día de corte ----------
    base = si.merge(reg, on=CLAVE, how='left').merge(cursos, on=['code_module', 'code_presentation'])
    base['dia_corte'] = (base['module_presentation_length'] * fraccion_corte).round()
    # quien se retiró antes del corte ya tiene resultado conocido: no se predice
    base = base[~(base['date_unregistration'] <= base['dia_corte'])].copy()

    # ---------- variables de perfil (reales, sin ruido) ----------
    base['nivel_educativo'] = base['highest_education'].map(ORD_EDU)
    base['banda_edad'] = base['age_band'].map(ORD_EDAD)
    base['indice_privacion_imd'] = base['imd_band'].map(ORD_IMD)          # NaN permitido
    base['discapacidad'] = (base['disability'] == 'Y').astype(int)
    base['intentos_previos'] = base['num_of_prev_attempts']
    base['creditos_matriculados'] = base['studied_credits']
    base['dias_registro_antes_inicio'] = -base['date_registration']       # >0 = se inscribió antes
    base['semestre_febrero'] = base['code_presentation'].str.endswith('B').astype(int)

    # ---------- actividad VLE hasta el corte ----------
    v = vle.merge(base[CLAVE + ['dia_corte']], on=CLAVE)
    v = v[v['date'] <= v['dia_corte']]
    g = v.groupby(CLAVE)
    act = pd.DataFrame({
        'clics_totales': g['sum_click'].sum(),
        'dias_activos': g['date'].nunique(),
        'clics_antes_inicio': v[v['date'] < 0].groupby(CLAVE)['sum_click'].sum(),
        'ultimo_dia_activo': g['date'].max(),
    })
    ult14 = v[v['date'] > v['dia_corte'] - 14].groupby(CLAVE)['sum_click'].sum()
    act['clics_ultimas_2_semanas'] = ult14
    v['semana'] = (v['date'] // 7).astype(int)
    act['semanas_activas'] = v.groupby(CLAVE)['semana'].nunique()
    # tendencia: clics de la 2.a mitad de la ventana vs 1.a mitad
    v['mitad2'] = v['date'] > v['dia_corte'] / 2
    m2 = v[v['mitad2']].groupby(CLAVE)['sum_click'].sum()
    m1 = v[~v['mitad2'] & (v['date'] >= 0)].groupby(CLAVE)['sum_click'].sum()
    act['tendencia_clics'] = (m2.reindex(act.index).fillna(0) + 1) / (m1.reindex(act.index).fillna(0) + 1)
    act = act.reset_index()
    base = base.merge(act, on=CLAVE, how='left')
    for c in ['clics_totales', 'dias_activos', 'clics_antes_inicio', 'clics_ultimas_2_semanas', 'semanas_activas']:
        base[c] = base[c].fillna(0)
    base['tendencia_clics'] = base['tendencia_clics'].fillna(1.0)
    base['dias_desde_ultima_actividad'] = (base['dia_corte'] - base['ultimo_dia_activo']).fillna(base['dia_corte'] + 30)
    base['clics_por_dia_activo'] = base['clics_totales'] / base['dias_activos'].replace(0, np.nan)
    base['clics_por_dia_activo'] = base['clics_por_dia_activo'].fillna(0)

    # ---------- evaluaciones con fecha límite antes del corte (sin examen final) ----------
    a = asses[asses['assessment_type'] != 'Exam'].copy()
    a = a.merge(cursos, on=['code_module', 'code_presentation'])
    a['date'] = a['date'].fillna(a['module_presentation_length'])
    eval_base = base[CLAVE + ['dia_corte']].merge(a, on=['code_module', 'code_presentation'])
    eval_base = eval_base[eval_base['date'] <= eval_base['dia_corte']]
    eval_base = eval_base.merge(sa, on=['id_student', 'id_assessment'], how='left')
    # una entrega hecha después del corte aún no se conoce en el momento de predecir
    no_visto = eval_base['date_submitted'] > eval_base['dia_corte']
    eval_base.loc[no_visto, ['date_submitted', 'score']] = np.nan
    eval_base['entregado'] = eval_base['date_submitted'].notna().astype(int)
    eval_base['nota'] = eval_base['score'].where(eval_base['entregado'] == 1, 0).fillna(0)
    eval_base['tarde'] = ((eval_base['date_submitted'] - eval_base['date']) > 0).astype(int)
    eval_base['dias_retraso'] = (eval_base['date_submitted'] - eval_base['date']).clip(lower=0)
    eval_base['nota_x_peso'] = eval_base['nota'] * eval_base['weight']
    eval_base['es_tma'] = (eval_base['assessment_type'] == 'TMA').astype(int)

    ge = eval_base.groupby(CLAVE)
    ev = pd.DataFrame({
        'evaluaciones_vencidas': ge['id_assessment'].count(),
        'evaluaciones_entregadas': ge['entregado'].sum(),
        'nota_promedio': ge['nota'].mean(),
        'nota_minima': ge['nota'].min(),
        'entregas_tardias': ge['tarde'].sum(),
        'retraso_promedio_dias': ge['dias_retraso'].mean(),
        'evaluaciones_reprobadas': eval_base.assign(r=(eval_base['nota'] < 40).astype(int)).groupby(CLAVE)['r'].sum(),
        'peso_vencido': ge['weight'].sum(),
        'nota_ponderada_acumulada': ge['nota_x_peso'].sum(),
    }).reset_index()
    ult = eval_base[eval_base['entregado'] == 1].sort_values('date').groupby(CLAVE)['nota'].last().rename('nota_ultima_evaluacion').reset_index()
    base = base.merge(ev, on=CLAVE, how='left').merge(ult, on=CLAVE, how='left')
    base['tasa_entrega'] = base['evaluaciones_entregadas'] / base['evaluaciones_vencidas'].replace(0, np.nan)
    base['nota_ponderada_relativa'] = base['nota_ponderada_acumulada'] / base['peso_vencido'].replace(0, np.nan)
    for c in ['evaluaciones_vencidas', 'evaluaciones_entregadas', 'entregas_tardias', 'evaluaciones_reprobadas',
              'peso_vencido', 'nota_ponderada_acumulada']:
        base[c] = base[c].fillna(0)
    # notas/retrasos sin evaluaciones vencidas quedan NaN (los modelos de boosting lo manejan;
    # para el resto se imputa en el pipeline de entrenamiento)

    base['resultado_final'] = base['final_result']
    columnas = CLAVE + FEATURES + ['resultado_final']
    return base[columnas].reset_index(drop=True)


FEATURES = [
    # perfil académico/demográfico (reales)
    'nivel_educativo', 'banda_edad', 'indice_privacion_imd', 'discapacidad',
    'intentos_previos', 'creditos_matriculados', 'dias_registro_antes_inicio', 'semestre_febrero',
    # comportamiento en el entorno virtual (clics reales)
    'clics_totales', 'dias_activos', 'clics_antes_inicio', 'clics_ultimas_2_semanas',
    'semanas_activas', 'tendencia_clics', 'dias_desde_ultima_actividad', 'clics_por_dia_activo',
    # desempeño en evaluaciones vencidas antes del corte
    'evaluaciones_vencidas', 'evaluaciones_entregadas', 'tasa_entrega', 'nota_promedio', 'nota_minima',
    'nota_ultima_evaluacion', 'entregas_tardias', 'retraso_promedio_dias', 'evaluaciones_reprobadas',
    'nota_ponderada_relativa',
]

if __name__ == '__main__':
    frac = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
    df = construir(frac)
    salida = f'dataset_estudiante_corte{int(frac * 100)}.csv'
    df.to_csv(salida, index=False)
    print(f'{len(df):,} estudiantes-curso | {len(FEATURES)} variables | corte al {frac:.0%} del curso')
    print(df['resultado_final'].value_counts(normalize=True).round(3))
    print(f'Guardado en {salida}')
