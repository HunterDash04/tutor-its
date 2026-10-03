"""
entrenar_modelo_a.py  (v2 — dataset a nivel estudiante, 3 estados cognitivos)

Diagnóstico del estado cognitivo del estudiante a mitad de curso (corte 50%).

Protocolo experimental (responde a los comentarios 40/45/50/56 de la asesora):
  1. Partición holdout 80/20 AGRUPADA por estudiante (un mismo estudiante nunca
     aparece en entrenamiento y prueba a la vez).
  2. Comparación de 9 algoritmos candidatos con validación cruzada estratificada
     y agrupada de 5 folds sobre el conjunto de entrenamiento.
  3. Selección del mejor por F1-macro (métrica robusta al desbalance de clases).
  4. Optimización de hiperparámetros del modelo seleccionado (RandomizedSearchCV,
     12 combinaciones, validación agrupada de 3 folds).
  5. Evaluación final una sola vez sobre el holdout + intervalo de confianza
     bootstrap (95%).
  6. Validación temporal: entrenar con cohortes 2013 y evaluar con cohortes 2014.
  7. Comparación contra un baseline trivial (clase mayoritaria).

Ejecutar desde la raíz del repositorio, después de:  py pipeline/construir_dataset_estudiante.py 0.5
Genera (en la carpeta resultados_modelo_a/):
  tabla_comparativa_modelos.csv, resultados_finales.txt, matriz_confusion.png,
  importancia_variables.png, comparacion_modelos.png
y en la raíz: modelo_diagnostico_final.pkl
"""
import os
import time
import json
import warnings
import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.model_selection import (StratifiedGroupKFold, GroupShuffleSplit,
                                     cross_validate, RandomizedSearchCV)
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import (RandomForestClassifier, ExtraTreesClassifier,
                              HistGradientBoostingClassifier)
from sklearn.neighbors import KNeighborsClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import LinearSVC
from sklearn.neural_network import MLPClassifier
from sklearn.dummy import DummyClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (accuracy_score, f1_score, balanced_accuracy_score,
                             cohen_kappa_score, classification_report,
                             confusion_matrix, ConfusionMatrixDisplay)

from construir_dataset_estudiante import FEATURES

warnings.filterwarnings('ignore')
SEMILLA = 42
DATASET = 'dataset_estudiante_corte50.csv'
SALIDA = 'resultados_modelo_a'

# Estados cognitivos del ITS (3 estados). Fail y Withdrawn se agrupan en "Riesgo":
# ambos requieren remediación y el comportamiento observable a mitad de curso no
# permite distinguirlos de forma fiable (F1 de Withdrawn = 0.10 en el experimento de 4 clases).
MAPEO_ESTADO = {
    'Withdrawn': 'Riesgo - Reforzar Fundamentos',
    'Fail': 'Riesgo - Reforzar Fundamentos',
    'Pass': 'Aprendizaje Normal - Mantener Ruta',
    'Distinction': 'Dominio Alto - Ruta Avanzada',
}
ORDEN_ESTADOS = ['Riesgo - Reforzar Fundamentos', 'Aprendizaje Normal - Mantener Ruta',
                 'Dominio Alto - Ruta Avanzada']


def preprocesador(escalar):
    num = [('imp', SimpleImputer(strategy='median'))]
    if escalar:
        num.append(('esc', StandardScaler()))
    return ColumnTransformer([
        ('num', Pipeline(num), FEATURES),
        ('mod', OneHotEncoder(handle_unknown='ignore'), ['code_module']),
    ])


def candidatos():
    m = {
        'Baseline (clase mayoritaria)': (DummyClassifier(strategy='most_frequent'), False),
        'Naive Bayes': (GaussianNB(), True),
        'Regresion Logistica': (LogisticRegression(max_iter=2000, class_weight='balanced'), True),
        'SVM lineal': (LinearSVC(C=0.5, class_weight='balanced', max_iter=5000), True),
        'K-Nearest Neighbors': (KNeighborsClassifier(n_neighbors=31, weights='distance'), True),
        'Arbol de Decision': (DecisionTreeClassifier(max_depth=8, min_samples_leaf=20,
                                                     class_weight='balanced', random_state=SEMILLA), False),
        'Random Forest': (RandomForestClassifier(n_estimators=300, min_samples_leaf=3,
                                                 class_weight='balanced_subsample',
                                                 random_state=SEMILLA, n_jobs=-1), False),
        'Extra Trees': (ExtraTreesClassifier(n_estimators=300, min_samples_leaf=3,
                                             class_weight='balanced', random_state=SEMILLA, n_jobs=-1), False),
        'Red Neuronal (MLP)': (MLPClassifier(hidden_layer_sizes=(64, 32), alpha=1e-3,
                                             early_stopping=True, max_iter=300, random_state=SEMILLA), True),
        'Gradient Boosting': (HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06,
                                                             class_weight='balanced',
                                                             random_state=SEMILLA), False),
    }
    try:
        from xgboost import XGBClassifier
        m['XGBoost'] = (XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=6,
                                      subsample=0.8, colsample_bytree=0.8, tree_method='hist',
                                      random_state=SEMILLA, n_jobs=-1, verbosity=0), False)
    except ImportError:
        print('(xgboost no instalado: se omite. Instálalo con "py -m pip install xgboost")')
    return m


def armar(modelo, escalar):
    return Pipeline([('pre', preprocesador(escalar)), ('clf', modelo)])


def metricas(y, p):
    return {
        'Accuracy': accuracy_score(y, p),
        'F1_macro': f1_score(y, p, average='macro'),
        'Balanced_accuracy': balanced_accuracy_score(y, p),
        'Kappa_Cohen': cohen_kappa_score(y, p),
    }


def bootstrap_ic(y, p, n=1000, semilla=SEMILLA):
    rng = np.random.default_rng(semilla)
    y, p = np.asarray(y), np.asarray(p)
    acc, f1 = [], []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        acc.append(accuracy_score(y[i], p[i]))
        f1.append(f1_score(y[i], p[i], average='macro'))
    return np.percentile(acc, [2.5, 97.5]), np.percentile(f1, [2.5, 97.5])


def main():
    os.makedirs(SALIDA, exist_ok=True)
    df = pd.read_csv(DATASET)
    df['estado'] = df['resultado_final'].map(MAPEO_ESTADO)
    clases = sorted(df['estado'].unique())
    a_num = {c: i for i, c in enumerate(clases)}
    X = df[FEATURES + ['code_module']]
    y = df['estado'].map(a_num).to_numpy()
    grupos = df['id_student'].to_numpy()

    print(f'Dataset: {len(df):,} estudiantes-curso, {len(FEATURES)} variables + módulo')
    print(df['estado'].value_counts(normalize=True).round(3).to_string(), '\n')

    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEMILLA)
    i_tr, i_te = next(gss.split(X, y, grupos))
    X_tr, X_te, y_tr, y_te, g_tr = X.iloc[i_tr], X.iloc[i_te], y[i_tr], y[i_te], grupos[i_tr]
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEMILLA)

    # ---------------- 1. Comparación de candidatos ----------------
    filas = []
    for nombre, (modelo, escalar) in candidatos().items():
        t0 = time.time()
        r = cross_validate(armar(modelo, escalar), X_tr, y_tr, groups=g_tr, cv=cv,
                           scoring={'acc': 'accuracy', 'f1m': 'f1_macro', 'bal': 'balanced_accuracy'},
                           n_jobs=1)
        filas.append({'Modelo': nombre,
                      'CV_Accuracy': r['test_acc'].mean(), 'CV_Accuracy_std': r['test_acc'].std(),
                      'CV_F1_macro': r['test_f1m'].mean(), 'CV_F1_macro_std': r['test_f1m'].std(),
                      'CV_Balanced_acc': r['test_bal'].mean(),
                      'Tiempo_s': time.time() - t0})
        print(f"{nombre:30s} acc={r['test_acc'].mean():.3f}±{r['test_acc'].std():.3f}  "
              f"F1m={r['test_f1m'].mean():.3f}±{r['test_f1m'].std():.3f}  ({time.time() - t0:.0f}s)")
    tabla = pd.DataFrame(filas).sort_values('CV_F1_macro', ascending=False).round(4)
    tabla.to_csv(f'{SALIDA}/tabla_comparativa_modelos.csv', index=False)

    # ---------------- 2. Selección + optimización ----------------
    ganador = tabla[tabla['Modelo'] != 'Baseline (clase mayoritaria)'].iloc[0]['Modelo']
    print(f'\nModelo seleccionado por F1-macro en CV: {ganador}')
    espacios = {
        'Gradient Boosting': {'clf__learning_rate': [0.03, 0.05, 0.08, 0.1],
                              'clf__max_iter': [200, 300, 500],
                              'clf__max_leaf_nodes': [15, 31, 63],
                              'clf__min_samples_leaf': [20, 50, 100],
                              'clf__l2_regularization': [0, 0.1, 1.0]},
        'XGBoost': {'clf__learning_rate': [0.03, 0.05, 0.1], 'clf__n_estimators': [200, 400, 600],
                    'clf__max_depth': [4, 6, 8], 'clf__subsample': [0.7, 0.8, 1.0],
                    'clf__colsample_bytree': [0.6, 0.8, 1.0], 'clf__min_child_weight': [1, 5, 10]},
        'Random Forest': {'clf__n_estimators': [200, 400], 'clf__max_depth': [None, 12, 20],
                          'clf__min_samples_leaf': [1, 3, 5, 10], 'clf__max_features': ['sqrt', 0.3]},
        'Extra Trees': {'clf__n_estimators': [200, 400], 'clf__max_depth': [None, 12, 20],
                        'clf__min_samples_leaf': [1, 3, 5, 10], 'clf__max_features': ['sqrt', 0.3]},
    }
    modelo_base, escalar = candidatos()[ganador]
    pipe = armar(modelo_base, escalar)
    if ganador in espacios:
        cv_busq = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=SEMILLA)
        busq = RandomizedSearchCV(pipe, espacios[ganador], n_iter=12, scoring='f1_macro',
                                  cv=cv_busq, random_state=SEMILLA, n_jobs=1, verbose=1)
        busq.fit(X_tr, y_tr, groups=g_tr)
        pipe = busq.best_estimator_
        mejores = {k.replace('clf__', ''): v for k, v in busq.best_params_.items()}
        print(f'Hiperparámetros óptimos: {mejores} (F1m CV={busq.best_score_:.4f})')
    else:
        mejores = {}
        pipe.fit(X_tr, y_tr)

    # ---------------- 3. Evaluación final en holdout ----------------
    p_te = pipe.predict(X_te)
    m_te = metricas(y_te, p_te)
    ic_acc, ic_f1 = bootstrap_ic(y_te, p_te)
    base_te = metricas(y_te, np.full_like(y_te, pd.Series(y_tr).mode()[0]))
    nombres_te = [clases[i] for i in y_te]
    nombres_pr = [clases[i] for i in p_te]
    reporte = classification_report(nombres_te, nombres_pr, digits=3)

    # ---------------- 4. Validación temporal 2013 -> 2014 ----------------
    anio = df['code_presentation'].str[:4]
    i13, i14 = np.where(anio == '2013')[0], np.where(anio == '2014')[0]
    pipe_t = armar(*candidatos()[ganador])
    if mejores:
        pipe_t.set_params(**{f'clf__{k}': v for k, v in mejores.items()})
    pipe_t.fit(X.iloc[i13], y[i13])
    m_temp = metricas(y[i14], pipe_t.predict(X.iloc[i14]))

    # ---------------- 5. Figuras ----------------
    cm = confusion_matrix(nombres_te, nombres_pr, labels=ORDEN_ESTADOS)
    fig, ax = plt.subplots(figsize=(7, 6))
    ConfusionMatrixDisplay(cm, display_labels=[e.split(' - ')[0] for e in ORDEN_ESTADOS]).plot(
        cmap='Blues', ax=ax, values_format='d', colorbar=False)
    ax.set_title(f'Matriz de confusión — {ganador} (holdout)')
    plt.tight_layout(); plt.savefig(f'{SALIDA}/matriz_confusion.png', dpi=200); plt.close()

    t = tabla[tabla['Modelo'] != 'Baseline (clase mayoritaria)'].sort_values('CV_F1_macro')
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(t['Modelo'], t['CV_F1_macro'], xerr=t['CV_F1_macro_std'], color='#4C72B0')
    base_f1 = tabla.loc[tabla['Modelo'] == 'Baseline (clase mayoritaria)', 'CV_F1_macro'].iloc[0]
    ax.axvline(base_f1, ls='--', color='gray', label=f'Baseline ({base_f1:.2f})')
    ax.set_xlabel('F1-macro (validación cruzada agrupada, 5 folds)'); ax.set_xlim(0, 0.85); ax.legend(loc='lower right')
    ax.set_title('Comparación de algoritmos — Modelo A')
    plt.tight_layout(); plt.savefig(f'{SALIDA}/comparacion_modelos.png', dpi=200); plt.close()

    imp = permutation_importance(pipe, X_te, y_te, scoring='f1_macro', n_repeats=5,
                                 random_state=SEMILLA, n_jobs=1)
    serie = pd.Series(imp.importances_mean, index=X_te.columns).sort_values().tail(15)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(serie.index, serie.values, color='#55A868')
    ax.set_xlabel('Caída de F1-macro al permutar la variable')
    ax.set_title('Importancia de variables por permutación (holdout)')
    plt.tight_layout(); plt.savefig(f'{SALIDA}/importancia_variables.png', dpi=200); plt.close()
    serie.sort_values(ascending=False).round(4).to_csv(f'{SALIDA}/importancia_variables.csv')

    # ---------------- 6. Modelo de producción ----------------
    pipe.fit(X, y)
    joblib.dump({'modelo': pipe, 'features': FEATURES + ['code_module'], 'clases': clases,
                 'nombre': ganador, 'hiperparametros': mejores, 'corte': 0.5},
                'modelo_diagnostico_final.pkl')

    texto = [
        '=' * 70, 'RESULTADOS FINALES — MODELO A (3 estados, corte 50% del curso)', '=' * 70,
        f'Estudiantes-curso: {len(df):,} | train: {len(i_tr):,} | holdout: {len(i_te):,} (agrupado por estudiante)',
        f'Modelo seleccionado: {ganador}', f'Hiperparámetros: {json.dumps(mejores, default=str)}', '',
        'HOLDOUT (evaluado una sola vez):',
        *[f'  {k}: {v:.4f}' for k, v in m_te.items()],
        f'  IC95% Accuracy: [{ic_acc[0]:.4f}, {ic_acc[1]:.4f}]',
        f'  IC95% F1-macro: [{ic_f1[0]:.4f}, {ic_f1[1]:.4f}]', '',
        'BASELINE clase mayoritaria (holdout):',
        *[f'  {k}: {v:.4f}' for k, v in base_te.items()], '',
        'VALIDACIÓN TEMPORAL (entrena 2013 -> evalúa 2014):',
        *[f'  {k}: {v:.4f}' for k, v in m_temp.items()], '',
        'Reporte por clase (holdout):', reporte,
    ]
    with open(f'{SALIDA}/resultados_finales.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(texto))
    print('\n'.join(texto))
    print(f'\nArchivos en {SALIDA}/ y modelo_diagnostico_final.pkl')


if __name__ == '__main__':
    main()
