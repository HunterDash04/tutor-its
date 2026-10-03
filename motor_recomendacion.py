"""
motor_recomendacion.py — Motor de recomendación HÍBRIDO entrenado con datos reales
de Codeforces (envíos reales de 1,500 usuarios y catálogo de problemas con etiquetas
y dificultad oficiales).

El motor estima, para cada problema candidato, la probabilidad de que el estudiante
lo resuelva al primer envío, P(éxito). Combina tres fuentes de información:

  1. ESTADO DEL ESTUDIANTE (knowledge tracing):
     - Habilidad global tipo Elo, actualizada después de cada intento.
     - Ajuste de habilidad por categoría y conteo de éxitos/fallos por categoría
       (estilo Performance Factors Analysis, Pavlik et al., 2009).
  2. CONTENIDO del problema: dificultad oficial (rating) y categorías temáticas.
  3. COLABORATIVO:
     - Dificultad colectiva: tasa de éxito al primer envío de OTROS usuarios en ese problema.
     - Factorización (SVD) de la matriz usuario × categoría: proyecta al estudiante en el
       espacio latente aprendido de otros usuarios y estima su dominio en cada categoría.

Un modelo de Gradient Boosting combina todas las variables (ver entrenar_recomendador.py).

La MISMA clase EstadoEstudiante se usa para construir los datos de entrenamiento
(reproduciendo el historial real de cada usuario) y en la sesión en vivo del simulador,
así el modelo ve exactamente las mismas variables en ambos casos.

Política de recomendación (Zona de Desarrollo Próximo): según el estado cognitivo
diagnosticado, se busca un problema cuya P(éxito) esté cerca de una meta:
  Riesgo  -> 0.75 (afianzar)      Normal -> 0.60 (progresar)      Dominio -> 0.45 (desafiar)
dentro de la categoría más débil (Riesgo/Normal) o de una categoría aún poco practicada.
"""
import math
from collections import defaultdict

import numpy as np
import pandas as pd
import joblib

from topicos_codeforces import CATEGORIAS, categorias_de

ELO_INICIAL = 1000.0
PRIOR_EXITO = 0.6     # tasa de éxito al primer envío promedio (suavizado bayesiano)
PESO_PRIOR = 3.0

FEATURES_RECOMENDADOR = [
    'rating_problema', 'rating_conocido', 'habilidad_elo', 'brecha_dificultad', 'prob_elo',
    'ajuste_categoria', 'intentos_previos_log', 'tasa_exito_global', 'exito_ultimos_5',
    'exitos_categoria', 'fallos_categoria', 'tasa_exito_categoria', 'tasa_exito_categoria_min',
    'n_categorias', 'dificultad_colectiva', 'intentos_colectivos_log', 'dominio_svd_categoria',
]

META_POR_ESTADO = {'Riesgo': 0.75, 'Aprendizaje Normal': 0.60, 'Dominio Alto': 0.45}


def _k(n):
    return 80.0 / (1.0 + 0.02 * n)


def prob_elo(habilidad, rating):
    return 1.0 / (1.0 + 10 ** ((rating - habilidad) / 400.0))


class EstadoEstudiante:
    """Estado de conocimiento de un estudiante, actualizado intento a intento."""

    def __init__(self, habilidad_inicial=ELO_INICIAL):
        self.habilidad = habilidad_inicial
        self.n = 0
        self.exitos = 0
        self.ultimos = []
        self.ajuste_cat = defaultdict(float)
        self.exitos_cat = defaultdict(int)
        self.fallos_cat = defaultdict(int)
        self.vistos = set()

    # ---------- variables para un problema candidato ----------
    def variables(self, rating, cats, stats_problema, colaborativo):
        conocido = rating is not None and not (isinstance(rating, float) and math.isnan(rating))
        r = float(rating) if conocido else self.habilidad
        ajuste = np.mean([self.ajuste_cat[c] for c in cats]) if cats else 0.0
        tasas = [(self.exitos_cat[c] + PRIOR_EXITO * PESO_PRIOR) /
                 (self.exitos_cat[c] + self.fallos_cat[c] + PESO_PRIOR) for c in cats] or [PRIOR_EXITO]
        dif_col, n_col = stats_problema
        return {
            'rating_problema': r if conocido else np.nan,
            'rating_conocido': int(conocido),
            'habilidad_elo': self.habilidad,
            'brecha_dificultad': r - self.habilidad,
            'prob_elo': prob_elo(self.habilidad + ajuste, r),
            'ajuste_categoria': ajuste,
            'intentos_previos_log': math.log1p(self.n),
            'tasa_exito_global': (self.exitos + PRIOR_EXITO * PESO_PRIOR) / (self.n + PESO_PRIOR),
            'exito_ultimos_5': np.mean(self.ultimos[-5:]) if self.ultimos else PRIOR_EXITO,
            'exitos_categoria': sum(self.exitos_cat[c] for c in cats),
            'fallos_categoria': sum(self.fallos_cat[c] for c in cats),
            'tasa_exito_categoria': float(np.mean(tasas)),
            'tasa_exito_categoria_min': float(np.min(tasas)),
            'n_categorias': len(cats),
            'dificultad_colectiva': dif_col,
            'intentos_colectivos_log': math.log1p(n_col),
            'dominio_svd_categoria': colaborativo.dominio_categorias(self, cats),
        }

    # ---------- actualización tras un intento real ----------
    def actualizar(self, rating, cats, exito_primer_envio, id_problema=None):
        y = 1.0 if exito_primer_envio else 0.0
        conocido = rating is not None and not (isinstance(rating, float) and math.isnan(rating))
        if conocido:
            ajuste = np.mean([self.ajuste_cat[c] for c in cats]) if cats else 0.0
            p = prob_elo(self.habilidad + ajuste, float(rating))
            k = _k(self.n)
            self.habilidad += k * (y - p)
            for c in cats:
                self.ajuste_cat[c] += 0.5 * k * (y - p)
        for c in cats:
            if y:
                self.exitos_cat[c] += 1
            else:
                self.fallos_cat[c] += 1
        self.n += 1
        self.exitos += int(y)
        self.ultimos.append(y)
        if id_problema is not None:
            self.vistos.add(id_problema)

    def dominio_por_categoria(self):
        return {c: (self.exitos_cat[c] + PRIOR_EXITO * PESO_PRIOR) /
                   (self.exitos_cat[c] + self.fallos_cat[c] + PESO_PRIOR) for c in CATEGORIAS}


class Colaborativo:
    """SVD sobre la matriz usuario x categoría (tasa de éxito suavizada) de los usuarios
    de entrenamiento. Para un estudiante nuevo se proyecta su vector al subespacio latente."""

    def __init__(self, Vt=None, medias=None):
        self.Vt, self.medias = Vt, medias

    def ajustar(self, matriz, k=4):
        from sklearn.decomposition import TruncatedSVD
        self.medias = matriz.mean(axis=0)
        svd = TruncatedSVD(n_components=k, random_state=42).fit(matriz - self.medias)
        self.Vt = svd.components_
        self.varianza = float(svd.explained_variance_ratio_.sum())
        return self

    def dominio_categorias(self, estado, cats):
        if self.Vt is None or not cats:
            return PRIOR_EXITO
        d = estado.dominio_por_categoria()
        v = np.array([d[c] for c in CATEGORIAS]) - self.medias
        rec = v @ self.Vt.T @ self.Vt + self.medias
        idx = [CATEGORIAS.index(c) for c in cats]
        return float(np.mean(rec[idx]))


class MotorRecomendacion:
    """Uso en vivo: carga el modelo entrenado y el catálogo, y recomienda el siguiente problema."""

    def __init__(self, ruta_pkl='motor_recomendacion.pkl'):
        a = joblib.load(ruta_pkl)
        self.modelo = a['modelo']
        self.colab = Colaborativo(a['svd_Vt'], a['svd_medias'])
        self.catalogo = a['catalogo']           # DataFrame: id_problema, nombre, rating, etiquetas, ...
        self.stats = a['stats_problemas']       # dict id_problema -> (dificultad_colectiva, n)
        self.prior_dif = a['prior_dificultad']
        self.catalogo['categorias'] = self.catalogo['etiquetas'].apply(categorias_de)
        self.catalogo = self.catalogo[self.catalogo['categorias'].str.len() > 0].reset_index(drop=True)

    def _stats(self, pid):
        return self.stats.get(pid, (self.prior_dif, 0))

    def probabilidades(self, estado, candidatos):
        filas = [estado.variables(r, cats, self._stats(pid), self.colab)
                 for pid, r, cats in zip(candidatos['id_problema'], candidatos['rating'], candidatos['categorias'])]
        X = pd.DataFrame(filas)[FEATURES_RECOMENDADOR]
        return self.modelo.predict_proba(X)[:, 1]

    def categoria_objetivo(self, estado, estado_cognitivo):
        dom = estado.dominio_por_categoria()
        practicadas = [c for c in CATEGORIAS if estado.exitos_cat[c] + estado.fallos_cat[c] > 0]
        if estado_cognitivo.startswith('Dominio'):
            # explorar: la categoría menos practicada
            return min(CATEGORIAS, key=lambda c: (estado.exitos_cat[c] + estado.fallos_cat[c], -dom[c]))
        if practicadas:
            return min(practicadas, key=lambda c: dom[c])  # la más débil
        return 'Implementación y Simulación'

    def recomendar(self, estado, estado_cognitivo, top_k=5, rng=None, max_candidatos=400):
        rng = rng or np.random.default_rng()
        clave = next((k for k in META_POR_ESTADO if estado_cognitivo.startswith(k)), 'Aprendizaje Normal')
        meta = META_POR_ESTADO[clave]
        cat = self.categoria_objetivo(estado, estado_cognitivo)
        cand = self.catalogo[self.catalogo['categorias'].apply(lambda cs: cat in cs)
                             & ~self.catalogo['id_problema'].isin(estado.vistos)]
        cand = cand[cand['rating'].notna()]
        # preselección por dificultad cercana a la habilidad (eficiencia), luego se puntúa con el modelo
        cand = cand.assign(_d=(cand['rating'] - estado.habilidad).abs()).nsmallest(max_candidatos, '_d')
        p = self.probabilidades(estado, cand)
        cand = cand.assign(p_exito=p, distancia_meta=np.abs(p - meta))
        top = cand.nsmallest(min(top_k, len(cand)), 'distancia_meta')
        elegido = top.iloc[rng.integers(len(top))]
        return elegido, cat, meta
