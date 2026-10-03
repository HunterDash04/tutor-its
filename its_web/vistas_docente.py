import os

import pandas as pd
import streamlit as st

from its_web import db, servicio
from its_web.vistas_estudiante import _fecha, progreso


def estudiantes():
    lista = db.listar_estudiantes()
    if not lista:
        st.info('Todavía no hay estudiantes registrados.')
        return
    filas = []
    for u in lista:
        if u['habilidad_inicial'] is None:
            filas.append({'Usuario': u['usuario'], 'Nombre': u['nombre'], 'Estado': 'Sin calibrar',
                          'Ejercicios': 0, 'Resueltos al 1er envío': '—', 'Habilidad': '—',
                          'Categoría más débil': '—', 'Último acceso': _fecha(u['ultimo_acceso'])})
            continue
        r = servicio.resumen(u)
        filas.append({'Usuario': u['usuario'], 'Nombre': u['nombre'], 'Estado': r['estado_cognitivo'].split(' - ')[0],
                      'Ejercicios': r['n_hechos'],
                      'Resueltos al 1er envío': f"{r['n_primer_envio'] / r['n_hechos']:.0%}" if r['n_hechos'] else '—',
                      'Habilidad': round(r['habilidad']), 'Categoría más débil': r['mas_debil'] or '—',
                      'Último acceso': _fecha(u['ultimo_acceso'])})
    tabla = pd.DataFrame(filas)
    c1, c2, c3 = st.columns(3)
    c1.metric('Estudiantes', len(tabla))
    c2.metric('En riesgo', int((tabla['Estado'] == 'Riesgo').sum()))
    c3.metric('Ejercicios registrados', int(tabla['Ejercicios'].sum()))
    st.dataframe(tabla, hide_index=True, width='stretch')

    st.markdown('#### Detalle de un estudiante')
    elegido = st.selectbox('Estudiante', [u['usuario'] for u in lista])
    u = next(x for x in lista if x['usuario'] == elegido)
    if u['habilidad_inicial'] is None:
        st.info('Este estudiante aún no completó su perfil inicial.')
    else:
        progreso(u)


def _mostrar(carpeta, archivo, tipo='texto'):
    ruta = os.path.join(carpeta, archivo)
    if not os.path.exists(ruta):
        st.warning(f'No se encontró {ruta}.')
        return
    if tipo == 'imagen':
        st.image(ruta, width='stretch')
    elif tipo == 'tabla':
        st.dataframe(pd.read_csv(ruta), hide_index=True, width='stretch')
    else:
        st.code(open(ruta, encoding='utf-8').read(), language=None)


def metricas():
    a, b = st.tabs(['Diagnóstico del estado cognitivo (OULAD)', 'Recomendador híbrido (Codeforces)'])
    with a:
        st.markdown('Comparación de algoritmos con validación cruzada agrupada por estudiante y evaluación final en datos no vistos.')
        _mostrar('resultados_modelo_a', 'tabla_comparativa_modelos.csv', 'tabla')
        c1, c2 = st.columns(2)
        with c1:
            _mostrar('resultados_modelo_a', 'comparacion_modelos.png', 'imagen')
        with c2:
            _mostrar('resultados_modelo_a', 'matriz_confusion.png', 'imagen')
        _mostrar('resultados_modelo_a', 'importancia_variables.png', 'imagen')
        with st.expander('Resultados completos'):
            _mostrar('resultados_modelo_a', 'resultados_finales.txt')
    with b:
        st.markdown('Predicción del éxito al primer envío en usuarios que el modelo nunca vio durante el entrenamiento.')
        _mostrar('resultados_recomendador', 'tabla_recomendador.csv', 'tabla')
        _mostrar('resultados_recomendador', 'comparacion_recomendador.png', 'imagen')
        with st.expander('Resultados completos'):
            _mostrar('resultados_recomendador', 'resultados_recomendador.txt')
