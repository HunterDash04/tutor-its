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
