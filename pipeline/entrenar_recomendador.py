"""
entrenar_recomendador.py — entrena y evalúa el motor de recomendación con datos
REALES de Codeforces (datasets/codeforces/, generados por descargar_codeforces.py).

Unidad de análisis: el PRIMER intento de un usuario en un problema.
Variable objetivo: ¿lo resolvió en su primer envío? (éxito al primer intento).

Protocolo:
  1. Se separan los usuarios 80/20 (los de prueba nunca se usan para entrenar ni para
     calcular estadísticas colaborativas).
  2. Para cada usuario se reproduce su historial en orden cronológico: las variables de
     cada intento se calculan SOLO con lo ocurrido antes (sin mirar el futuro). La
     dificultad colectiva de los problemas se calcula siempre con OTROS usuarios
     (fuera de pliegue en entrenamiento; solo usuarios de entrenamiento en la prueba).
  3. Se comparan: azar, dificultad colectiva, Elo, PFA (regresión logística),
     regresión logística completa, Random Forest y Gradient Boosting híbrido.
  4. Evaluación en usuarios de prueba: AUC, log-loss, Brier, accuracy, IC95% bootstrap
     por usuario, calibración (¿si predice 70%, acierta ~70%?) y detección de los
     problemas que el estudiante fallará (Precision@5 frente al azar, Wilcoxon).

  5. Ajuste de hiperparámetros del modelo híbrido (RandomizedSearchCV con validación
     agrupada por usuario, solo con usuarios de entrenamiento).
  6. Calibración del diagnóstico en vivo: el estado del estudiante se define como su
     rendimiento reciente respecto de lo esperado (media móvil exponencial del residuo
     éxito − P(éxito)). Los umbrales se fijan por cuantiles para reproducir la proporción
     de estados observada en OULAD (Riesgo/Normal/Dominio), y se verifica que el estado
     aporte información para predecir el siguiente intento (prueba de razón de verosimilitud).

Genera resultados_recomendador/, motor_recomendacion.pkl y calibracion_diagnostico.json
(los usan la app y el simulador).
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # módulos compartidos con la app
import time
import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json
from scipy.stats import wilcoxon, chi2
from sklearn.model_selection import GroupShuffleSplit, GroupKFold, RandomizedSearchCV
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, log_loss, brier_score_loss, accuracy_score

from topicos_codeforces import CATEGORIAS, categorias_de
from motor_recomendacion import (EstadoEstudiante, Colaborativo, FEATURES_RECOMENDADOR,
                                 PRIOR_EXITO, PESO_PRIOR)

SEMILLA = 42
CARPETA = os.path.join('datasets', 'codeforces')
SALIDA = 'resultados_recomendador'
VEREDICTOS_IGNORADOS = {'COMPILATION_ERROR', 'SKIPPED', 'TESTING', 'REJECTED'}


def cargar_intentos():
    e = pd.read_csv(os.path.join(CARPETA, 'envios_codeforces.csv'))
    e = e[~e['veredicto'].isin(VEREDICTOS_IGNORADOS)].sort_values(['id_usuario', 'tiempo_unix', 'id_envio'])
    primero = e.groupby(['id_usuario', 'id_problema'], sort=False).first().reset_index()
    primero['exito'] = (primero['veredicto'] == 'OK').astype(int)
    primero['categorias'] = primero['etiquetas'].apply(categorias_de)
    primero = primero[primero['categorias'].str.len() > 0]
    return primero.sort_values(['id_usuario', 'tiempo_unix']).reset_index(drop=True)


def stats_colectivas(df):
    g = df.groupby('id_problema')['exito'].agg(['sum', 'count'])
    return g


def matriz_usuario_categoria(df):
    filas = []
    for uid, g in df.groupby('id_usuario'):
        ex, to = defaultdict_int(), defaultdict_int()
        for cats, y in zip(g['categorias'], g['exito']):
            for c in cats:
                to[c] += 1
                ex[c] += y
        filas.append([(ex[c] + PRIOR_EXITO * PESO_PRIOR) / (to[c] + PESO_PRIOR) for c in CATEGORIAS])
    return np.array(filas)


def defaultdict_int():
    from collections import defaultdict
    return defaultdict(int)


def reproducir(df, stats, prior_dif, colab):
    """Recorre el historial de cada usuario y calcula las variables antes de cada intento."""
    filas = []
    st = {pid: (int(r[0]), int(r[1])) for pid, r in zip(stats.index, stats[['sum', 'count']].to_numpy())}
    for uid, g in df.groupby('id_usuario', sort=False):
        est = EstadoEstudiante()
        for pid, rating, cats, y in zip(g['id_problema'], g['rating_problema'], g['categorias'], g['exito']):
            s, n = st.get(pid, (0, 0))
            dif = (s + prior_dif * 5) / (n + 5)
            v = est.variables(rating, cats, (dif, n), colab)
            v.update(id_usuario=uid, id_problema=pid, exito=y)
            filas.append(v)
            est.actualizar(rating, cats, y, pid)
    return pd.DataFrame(filas)


def reproducir_fuera_de_pliegue(df, prior_dif, colab, k=5):
    """Para los usuarios de entrenamiento, la dificultad colectiva de cada problema se
    calcula con los OTROS pliegues de usuarios (nunca con el propio usuario), para que el
    modelo aprenda con la misma clase de información que tendrá con un estudiante nuevo."""
    usuarios = df['id_usuario'].unique()
    pliegue = dict(zip(usuarios, np.random.default_rng(SEMILLA).integers(0, k, len(usuarios))))
    f = df['id_usuario'].map(pliegue)
    partes = []
    for i in range(k):
        partes.append(reproducir(df[f == i], stats_colectivas(df[f != i]), prior_dif, colab))
    return pd.concat(partes, ignore_index=True)


def metricas(y, p):
    return {'AUC': roc_auc_score(y, p), 'LogLoss': log_loss(y, np.clip(p, 1e-6, 1 - 1e-6)),
            'Brier': brier_score_loss(y, p), 'Accuracy': accuracy_score(y, p >= 0.5)}


def ic_bootstrap_usuarios(te, col, n=300):
    rng = np.random.default_rng(SEMILLA)
    usuarios = te['id_usuario'].unique()
    grupos = {u: g for u, g in te.groupby('id_usuario')}
    aucs = []
    for _ in range(n):
        m = pd.concat([grupos[u] for u in rng.choice(usuarios, len(usuarios))])
        aucs.append(roc_auc_score(m['exito'], m[col]))
    return np.percentile(aucs, [2.5, 97.5])


def precision_fallos(te, col, k=5):
    """Por usuario: en su segunda mitad de intentos, ordenar por P(éxito) ascendente
    y ver cuántos de los k primeros realmente los falló."""
    res, azar = [], []
    rng = np.random.default_rng(SEMILLA)
    for _, g in te.groupby('id_usuario'):
        g = g.iloc[len(g) // 2:]
        if len(g) < 2 * k or g['exito'].all() or not g['exito'].any():
            continue
        fallo = 1 - g['exito'].to_numpy()
        res.append(fallo[np.argsort(g[col].to_numpy(), kind='stable')[:k]].mean())
        azar.append(fallo[rng.permutation(len(g))[:k]].mean())
    return np.array(res), np.array(azar)


# Proporción de estados en OULAD (dataset_estudiante_corte50.csv): Fail+Withdrawn / Pass / Distinction
PREVALENCIA_OULAD = {'Riesgo': 0.375, 'Normal': 0.502, 'Dominio': 0.123}
ALFA_DIAGNOSTICO = 0.2
BASE_GB = dict(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=50, random_state=SEMILLA)
ESPACIO_GB = {'learning_rate': [0.03, 0.05, 0.08, 0.1], 'max_iter': [200, 400, 700],
              'max_leaf_nodes': [15, 31, 63], 'min_samples_leaf': [20, 50, 100, 200],
              'l2_regularization': [0.0, 0.1, 1.0]}


def ajustar_hiperparametros(X, y, grupos, n_iter=12):
    busq = RandomizedSearchCV(HistGradientBoostingClassifier(random_state=SEMILLA), ESPACIO_GB, n_iter=n_iter,
                              scoring='roc_auc', cv=GroupKFold(n_splits=3), random_state=SEMILLA, n_jobs=1, verbose=1)
    busq.fit(X, y, groups=grupos)
    return busq.best_params_, busq.best_score_


def indice_rendimiento(g, col_p, alfa=ALFA_DIAGNOSTICO):
    """Media móvil exponencial del residuo (éxito − P predicha), empezando en 0 (neutral)."""
    v, out = 0.0, []
    for y, p in zip(g['exito'].to_numpy(), g[col_p].to_numpy()):
        v = alfa * (y - p) + (1 - alfa) * v
        out.append(v)
    return out


def calibrar_diagnostico(te, col_p):
    te = te.copy()
    te['indice'] = np.concatenate([indice_rendimiento(g, col_p) for _, g in te.groupby('id_usuario', sort=False)])
    u_riesgo, u_dominio = np.quantile(te['indice'], [PREVALENCIA_OULAD['Riesgo'], 1 - PREVALENCIA_OULAD['Dominio']])
    te['estado'] = np.where(te['indice'] < u_riesgo, 'Riesgo',
                            np.where(te['indice'] > u_dominio, 'Dominio Alto', 'Aprendizaje Normal'))
    g = te.groupby('id_usuario', sort=False)
    te['exito_siguiente'] = g['exito'].shift(-1)
    te['p_siguiente'] = g[col_p].shift(-1)
    d = te.dropna(subset=['exito_siguiente'])
    validez = d.groupby('estado').agg(n=('exito_siguiente', 'size'), exito_siguiente=('exito_siguiente', 'mean'),
                                      p_predicha_siguiente=('p_siguiente', 'mean'))
    validez = validez.reindex(['Riesgo', 'Aprendizaje Normal', 'Dominio Alto']).round(3)
    # ¿el índice aporta información más allá de la probabilidad del modelo? (razón de verosimilitud)
    lp = np.log(np.clip(d['p_siguiente'], 1e-6, 1 - 1e-6) / np.clip(1 - d['p_siguiente'], 1e-6, 1))
    y = d['exito_siguiente'].astype(int)
    X0, X1 = lp.to_frame('lp'), pd.DataFrame({'lp': lp, 'indice': d['indice']})
    ll = lambda X: -log_loss(y, LogisticRegression(C=1e6, max_iter=1000).fit(X, y).predict_proba(X)[:, 1]) * len(y)
    lr = 2 * (ll(X1) - ll(X0))
    return {'alfa': ALFA_DIAGNOSTICO, 'umbral_riesgo': float(u_riesgo), 'umbral_dominio': float(u_dominio),
            'prevalencia_objetivo': PREVALENCIA_OULAD, 'razon_verosimilitud': float(lr),
            'p_valor': float(chi2.sf(lr, 1))}, validez


def main():
    os.makedirs(SALIDA, exist_ok=True)
    t0 = time.time()
    df = cargar_intentos()
    print(f'{len(df):,} primeros intentos | {df.id_usuario.nunique():,} usuarios | '
          f'{df.id_problema.nunique():,} problemas | éxito al primer envío: {df.exito.mean():.3f}')

    usuarios = df['id_usuario'].to_numpy()
    i_tr, i_te = next(GroupShuffleSplit(1, test_size=0.2, random_state=SEMILLA).split(df, groups=usuarios))
    tr_raw, te_raw = df.iloc[i_tr], df.iloc[i_te]

    stats = stats_colectivas(tr_raw)
    prior_dif = tr_raw['exito'].mean()
    colab = Colaborativo().ajustar(matriz_usuario_categoria(tr_raw))
    print(f'SVD usuario x categoría: varianza explicada {colab.varianza:.1%}')

    print('Reproduciendo historiales (variables calculadas solo con el pasado)...')
    tr = reproducir_fuera_de_pliegue(tr_raw, prior_dif, colab)
    te = reproducir(te_raw, stats, prior_dif, colab)
    X_tr, y_tr, X_te, y_te = tr[FEATURES_RECOMENDADOR], tr['exito'], te[FEATURES_RECOMENDADOR], te['exito']
    print(f'Train: {len(tr):,} intentos ({tr.id_usuario.nunique()} usuarios) | '
          f'Prueba: {len(te):,} intentos ({te.id_usuario.nunique()} usuarios)  [{time.time() - t0:.0f}s]')

    print('Ajustando hiperparámetros del modelo híbrido (solo usuarios de entrenamiento)...')
    t1 = time.time()
    mejores, auc_cv = ajustar_hiperparametros(X_tr, y_tr, tr['id_usuario'].to_numpy())
    print(f'  Mejores hiperparámetros: {mejores} (AUC CV={auc_cv:.4f}) [{time.time() - t1:.0f}s]')

    pfa = ['exitos_categoria', 'fallos_categoria', 'brecha_dificultad']
    modelos = {
        'PFA (regresión logística)': (make_pipeline(SimpleImputer(), StandardScaler(),
                                                    LogisticRegression(max_iter=1000)), pfa),
        'Regresión logística (todas)': (make_pipeline(SimpleImputer(), StandardScaler(),
                                                      LogisticRegression(max_iter=1000)), FEATURES_RECOMENDADOR),
        'Random Forest': (make_pipeline(SimpleImputer(), RandomForestClassifier(
            n_estimators=200, min_samples_leaf=20, n_jobs=-1, random_state=SEMILLA)), FEATURES_RECOMENDADOR),
        'Híbrido sin ajustar': (HistGradientBoostingClassifier(**BASE_GB), FEATURES_RECOMENDADOR),
        'Híbrido (Gradient Boosting)': (HistGradientBoostingClassifier(random_state=SEMILLA, **mejores),
                                        FEATURES_RECOMENDADOR),
    }
    rng = np.random.default_rng(SEMILLA)
    te['p_Azar'] = rng.random(len(te))
    te['p_Dificultad colectiva'] = te['dificultad_colectiva']
    te['p_Elo (habilidad vs dificultad)'] = te['prob_elo']
    for nombre, (m, cols) in modelos.items():
        t1 = time.time()
        m.fit(X_tr[cols], y_tr)
        te[f'p_{nombre}'] = m.predict_proba(X_te[cols])[:, 1]
        print(f'  {nombre}: entrenado en {time.time() - t1:.0f}s')

    filas = []
    for c in [c for c in te.columns if c.startswith('p_')]:
        fila = {'Método': c[2:], **metricas(y_te, te[c])}
        prec, azar = precision_fallos(te, c)
        fila['Precision@5_fallos'] = prec.mean()
        filas.append(fila)
    tabla = pd.DataFrame(filas).sort_values('AUC').round(4)
    tabla.to_csv(f'{SALIDA}/tabla_recomendador.csv', index=False)
    print('\n' + tabla.to_string(index=False))

    mejor = 'p_Híbrido (Gradient Boosting)'
    ic = ic_bootstrap_usuarios(te, mejor)
    ic_elo = ic_bootstrap_usuarios(te, 'p_Elo (habilidad vs dificultad)')
    prec, azar = precision_fallos(te, mejor)
    w, pval = wilcoxon(prec, azar, alternative='greater')

    # calibración: ¿la probabilidad predicha coincide con lo que realmente ocurre?
    bins = pd.cut(te[mejor], [0, .2, .3, .4, .5, .6, .7, .8, .9, 1.0])
    calib = te.groupby(bins, observed=True).agg(predicho=(mejor, 'mean'), real=('exito', 'mean'),
                                                n=('exito', 'size')).round(3)
    calib.to_csv(f'{SALIDA}/calibracion.csv')

    calib_diag, validez = calibrar_diagnostico(te, mejor)
    validez.to_csv(f'{SALIDA}/validez_diagnostico.csv')
    with open('calibracion_diagnostico.json', 'w', encoding='utf-8') as f:
        json.dump(calib_diag, f, ensure_ascii=False, indent=2)

    texto = (f"\nHiperparámetros del modelo híbrido: {mejores} (AUC CV={auc_cv:.4f})\n"
             f"\nModelo híbrido — AUC {tabla.set_index('Método').loc['Híbrido (Gradient Boosting)', 'AUC']:.4f} "
             f"(IC95% por usuarios: [{ic[0]:.4f}, {ic[1]:.4f}])\n"
             f"Elo solo — IC95% AUC: [{ic_elo[0]:.4f}, {ic_elo[1]:.4f}]\n"
             f"Detección de problemas que el estudiante fallará (Precision@5, {len(prec)} usuarios): "
             f"híbrido {prec.mean():.3f} vs azar {azar.mean():.3f}; Wilcoxon W={w:.0f}, p={pval:.2e}\n"
             f"\nCalibración (prob. predicha vs tasa real de éxito):\n{calib.to_string()}\n"
             f"\nDIAGNÓSTICO EN VIVO (calibrado con usuarios de prueba)\n"
             f"Índice = media móvil (alfa={calib_diag['alfa']}) de éxito − P(éxito). "
             f"Umbrales: Riesgo < {calib_diag['umbral_riesgo']:.4f} < Normal < {calib_diag['umbral_dominio']:.4f} < Dominio\n"
             f"Información adicional del índice para predecir el siguiente intento: "
             f"LR={calib_diag['razon_verosimilitud']:.1f}, p={calib_diag['p_valor']:.2e}\n"
             f"Éxito real en el intento siguiente según el estado:\n{validez.to_string()}\n")
    print(texto)
    with open(f'{SALIDA}/resultados_recomendador.txt', 'w', encoding='utf-8') as f:
        f.write(f'Datos: {len(df):,} primeros intentos reales, {df.id_usuario.nunique()} usuarios, '
                f'{df.id_problema.nunique()} problemas (Codeforces).\n'
                f'Usuarios de prueba (nunca vistos en entrenamiento): {te.id_usuario.nunique()}\n\n')
        f.write(tabla.to_string(index=False) + '\n' + texto)

    # figuras
    t = tabla[tabla['Método'] != 'Azar']
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    ax[0].barh(t['Método'], t['AUC'], color='#4C72B0'); ax[0].axvline(0.5, ls='--', c='gray', label='Azar (0.50)')
    ax[0].set_xlim(0.45, max(t['AUC']) + 0.05); ax[0].set_xlabel('AUC (usuarios de prueba)'); ax[0].legend(loc='lower right')
    ax[0].set_title('Predicción de éxito al primer envío')
    ax[1].plot([0, 1], [0, 1], '--', c='gray', label='Calibración perfecta')
    ax[1].plot(calib['predicho'], calib['real'], 'o-', c='#55A868', label='Modelo híbrido')
    ax[1].set_xlabel('Probabilidad predicha'); ax[1].set_ylabel('Tasa real de éxito'); ax[1].legend()
    ax[1].set_title('Calibración')
    plt.tight_layout(); plt.savefig(f'{SALIDA}/comparacion_recomendador.png', dpi=200); plt.close()

    # modelo final con todos los usuarios
    print('Entrenando modelo final con todos los usuarios...')
    stats_all = stats_colectivas(df)
    prior_all = df['exito'].mean()
    colab_all = Colaborativo().ajustar(matriz_usuario_categoria(df))
    todo = reproducir_fuera_de_pliegue(df, prior_all, colab_all)
    final = HistGradientBoostingClassifier(random_state=SEMILLA, **mejores)
    final.fit(todo[FEATURES_RECOMENDADOR], todo['exito'])
    catalogo = pd.read_csv(os.path.join(CARPETA, 'problemas_codeforces.csv'))
    catalogo = catalogo.rename(columns={'rating': 'rating'})[['id_problema', 'nombre', 'rating', 'etiquetas', 'veces_resuelto']]
    stats_dict = {pid: ((r['sum'] + prior_all * 5) / (r['count'] + 5), int(r['count']))
                  for pid, r in stats_all.iterrows()}
    joblib.dump({'modelo': final, 'svd_Vt': colab_all.Vt, 'svd_medias': colab_all.medias,
                 'catalogo': catalogo, 'stats_problemas': stats_dict, 'prior_dificultad': prior_all,
                 'features': FEATURES_RECOMENDADOR, 'hiperparametros': mejores,
                 'diagnostico': calib_diag}, 'motor_recomendacion.pkl')
    print(f'Guardado motor_recomendacion.pkl, calibracion_diagnostico.json y {SALIDA}/  [{time.time() - t0:.0f}s total]')


if __name__ == '__main__':
    main()
