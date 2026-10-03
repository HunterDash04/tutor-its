import datetime as dt

import altair as alt
import pandas as pd
import streamlit as st

from its_web import db, seguridad, servicio
from its_web.codeforces import ErrorCodeforces, validar_handle, verificar_envios
from topicos_codeforces import categorias_de, url_problema

ICONO_ESTADO = {
    'Riesgo': '<span style="color:#E8A33D">●</span>',
    'Aprendizaje Normal': '<span style="color:#4C72B0">●</span>',
    'Dominio Alto': '<span style="color:#3FA34D">●</span>',
}


def _icono(estado):
    return next((v for k, v in ICONO_ESTADO.items() if estado.startswith(k)),
                '<span style="color:#4C72B0">●</span>')


def _fecha(ts):
    return dt.datetime.fromtimestamp(ts).strftime('%d/%m/%Y %H:%M') if ts else '—'


def _min(seg):
    return f'{seg // 60} min {seg % 60:02d} s' if seg is not None else '—'


def bienvenida(usuario):
    st.subheader(f'Hola, {usuario["nombre"] or usuario["usuario"]}')
    st.write('Antes de empezar, necesitamos calibrar tu punto de partida.')
    with st.form('perfil_inicial'):
        nombre = st.text_input('Nombre completo', value=usuario['nombre'] or '')
        gpa = st.number_input('Promedio ponderado (escala 0–20)', 0.0, 20.0, 13.0, 0.1)
        handle = st.text_input('Usuario de Codeforces (opcional)',
                               help='Si lo vinculas, el sistema podrá verificar tus envíos automáticamente.')
        enviar = st.form_submit_button('Empezar', type='primary')
    if enviar:
        cambios = {'nombre': nombre.strip(), 'gpa': float(gpa)}
        cambios['habilidad_inicial'], perfil = servicio.habilidad_inicial(gpa)
        if handle.strip():
            try:
                cambios['handle_cf'] = validar_handle(handle)
            except ErrorCodeforces as e:
                st.error(f'No se pudo vincular "{handle}": {e}')
                return
        db.actualizar_usuario(usuario['id'], **cambios)
        st.success(f'Perfil calibrado: {perfil}.')
        st.rerun()


_CSS_TARJETA = ('border:1px solid rgba(128,128,128,.25);border-radius:12px;padding:14px 16px;height:100%')


def _tarjeta(col, titulo, valor, detalle=''):
    col.markdown(f"<div style='{_CSS_TARJETA}'><div style='font-size:.8rem;opacity:.7'>{titulo}</div>"
                 f"<div style='font-size:1.25rem;font-weight:600;margin-top:4px'>{valor}</div>"
                 f"<div style='font-size:.78rem;opacity:.65;margin-top:2px'>{detalle}</div></div>",
                 unsafe_allow_html=True)


def _tarjetas(res):
    c1, c2, c3, c4 = st.columns(4)
    estado = res['estado_cognitivo'].split(' - ')
    _tarjeta(c1, 'Estado actual', f"{_icono(res['estado_cognitivo'])} {estado[0]}",
             estado[1] if len(estado) > 1 else '')
    _tarjeta(c2, 'Habilidad estimada', f"{res['habilidad']:.0f}", 'escala de dificultad de Codeforces')
    _tarjeta(c3, 'Problemas resueltos', f"{res['n_resueltos']} / {res['n_hechos']}",
             f"{res['n_primer_envio']} al primer envío")
    _tarjeta(c4, 'Categoría más débil', res['mas_debil'] or 'Aún sin datos', 'se priorizará en tu ruta')
    st.write('')


def practicar(motor, usuario):
    res = servicio.resumen(usuario)
    _tarjetas(res)
    if 'ultimo_diagnostico' in st.session_state:
        d = st.session_state.pop('ultimo_diagnostico')
        st.info(d)

    it = servicio.recomendacion_actual(motor, usuario)
    st.divider()
    izq, der = st.columns([3, 2], gap='large')
    with izq:
        st.markdown('#### Tu siguiente ejercicio')
        st.markdown(f"### {it['id_problema']} · {it['nombre_problema']}")
        etiquetas = ', '.join(it['etiquetas'].split(';'))
        st.markdown(f"**Dificultad:** {it['rating']:.0f}  ·  **Temas:** {etiquetas}")
        st.markdown(f"**Categorías:** {', '.join(categorias_de(it['etiquetas']))}")
        st.link_button('Abrir el enunciado en Codeforces ↗', url_problema(it['id_problema']), type='primary')
        st.caption(f"Mostrado el {_fecha(it['mostrado_en'])}. El tiempo se mide automáticamente desde ese momento.")
        with st.expander('¿Por qué este ejercicio?'):
            st.markdown(servicio.motivo(it['estado_previo'], it['categoria_objetivo'], it['meta']))
            st.markdown(f"Probabilidad estimada de que lo resuelvas al primer envío: **{it['p_exito']:.0%}**.")

    with der:
        st.markdown('#### Registrar resultado')
        if usuario.get('handle_cf'):
            st.caption(f"Cuenta de Codeforces vinculada: **{usuario['handle_cf']}**")
            if st.button('Verificar en Codeforces', width='stretch'):
                try:
                    r = verificar_envios(usuario['handle_cf'], it['id_problema'], it['mostrado_en'])
                except ErrorCodeforces as e:
                    st.error(str(e))
                else:
                    if not r['encontrado']:
                        st.warning('Todavía no hay envíos tuyos a este problema desde que se te recomendó.')
                    elif r['resuelto']:
                        diag = servicio.registrar(usuario, it, 'resuelto', r['envios'], 'codeforces', r['tiempo_s'])
                        st.session_state['ultimo_diagnostico'] = (
                            f"Verificado en Codeforces: resuelto en {r['envios']} envío(s), "
                            f"{_min(r['tiempo_s'])}. Nuevo estado: {diag}.")
                        st.rerun()
                    else:
                        st.warning(f"Encontramos {r['envios']} envío(s) sin aceptar (último: {r['ultimo_veredicto']}). "
                                   'Sigue intentando, o regístralo como no resuelto abajo.')
            st.caption('…o regístralo manualmente:')
        with st.form('resultado_manual', clear_on_submit=True):
            resultado = st.radio('¿Lo resolviste?', ['Sí', 'No'], horizontal=True)
            envios = st.number_input('Número de envíos realizados', 1, 100, 1)
            ok = st.form_submit_button('Registrar', type='primary', width='stretch')
        if ok:
            diag = servicio.registrar(usuario, it, 'resuelto' if resultado == 'Sí' else 'no_resuelto', envios, 'manual')
            st.session_state['ultimo_diagnostico'] = f'Resultado registrado. Nuevo estado: {diag}.'
            st.rerun()
        if st.button('Saltar este ejercicio', width='stretch'):
            servicio.registrar(usuario, it, 'omitido', None, 'manual')
            st.session_state['ultimo_diagnostico'] = 'Ejercicio omitido. No afecta tu estimación de habilidad.'
            st.rerun()


def progreso(usuario):
    res = servicio.resumen(usuario)
    _tarjetas(res)
    hechos = [h for h in res['historial'] if h['resultado'] in ('resuelto', 'no_resuelto')]
    if not hechos:
        st.info('Aún no registraste ejercicios. Tu progreso aparecerá aquí.')
        return

    c1, c2 = st.columns(2, gap='large')
    with c1:
        st.markdown('#### Evolución de tu habilidad')
        evo = pd.DataFrame({'Ejercicio': range(0, len(hechos) + 1),
                            'Habilidad': [usuario['habilidad_inicial']] + [h['habilidad_despues'] for h in hechos]})
        st.altair_chart(alt.Chart(evo).mark_line(point=True).encode(
            x=alt.X('Ejercicio:Q', axis=alt.Axis(tickMinStep=1)),
            y=alt.Y('Habilidad:Q', scale=alt.Scale(zero=False))), width='stretch')
    with c2:
        st.markdown('#### Dominio por categoría')
        dom = res['dominio'].copy()
        dom['Estado'] = dom['Problemas'].map(lambda n: 'Practicada' if n else 'Sin practicar')
        dom = dom.sort_values(['Estado', 'Dominio estimado'], ascending=[True, True])
        st.altair_chart(alt.Chart(dom).mark_bar().encode(
            x=alt.X('Dominio estimado:Q', scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format='%')),
            y=alt.Y('Categoría:N', sort=list(dom['Categoría']), title=None, axis=alt.Axis(labelLimit=260)),
            color=alt.Color('Estado:N', scale=alt.Scale(range=['#4C72B0', '#C7CED8'])),
            tooltip=['Categoría', alt.Tooltip('Dominio estimado:Q', format='.0%'), 'Problemas']),
            width='stretch')
        st.caption('Dominio = probabilidad estimada de resolver un problema de esa categoría al primer envío.')

    st.markdown('#### Tu ruta de aprendizaje')
    filas = [{'#': i, 'Problema': f"{h['id_problema']} · {h['nombre_problema']}", 'Dificultad': int(h['rating']),
              'Categoría objetivo': h['categoria_objetivo'],
              'Resultado': {'resuelto': '✔ Resuelto', 'no_resuelto': '✘ No resuelto',
                            'omitido': '→ Omitido'}[h['resultado']],
              'Envíos': str(h['envios']) if h['envios'] else '—', 'Tiempo': _min(h['tiempo_s']),
              'Registro': 'Codeforces' if h['modo'] == 'codeforces' else 'Manual',
              'Estado después': h['estado_resultante'] or '—', 'Fecha': _fecha(h['registrado_en'])}
             for i, h in enumerate([h for h in res['historial'] if h['registrado_en']], 1)]
    st.dataframe(pd.DataFrame(filas), hide_index=True, width='stretch')


def cuenta(usuario):
    st.markdown('#### Mi cuenta')
    st.write(f"Usuario: **{usuario['usuario']}** · Registrado el {_fecha(usuario['creado_en'])}")
    st.write(f"Promedio inicial: **{usuario['gpa']}**")
    with st.form('vincular'):
        handle = st.text_input('Usuario de Codeforces', value=usuario.get('handle_cf') or '')
        guardar = st.form_submit_button('Guardar')
    if guardar:
        if not handle.strip():
            db.actualizar_usuario(usuario['id'], handle_cf=None)
            st.success('Cuenta de Codeforces desvinculada.')
        else:
            try:
                db.actualizar_usuario(usuario['id'], handle_cf=validar_handle(handle))
                st.success('Cuenta de Codeforces vinculada.')
            except ErrorCodeforces as e:
                st.error(f'No se pudo vincular: {e}')

    st.markdown('#### Cambiar contraseña')
    with st.form('cambiar_clave', clear_on_submit=True):
        actual = st.text_input('Contraseña actual', type='password')
        nueva = st.text_input('Nueva contraseña (mínimo 8 caracteres)', type='password')
        nueva2 = st.text_input('Repite la nueva contraseña', type='password')
        cambiar = st.form_submit_button('Cambiar contraseña')
    if cambiar:
        error = None if seguridad.verificar(actual, usuario['hash']) else 'La contraseña actual no es correcta.'
        error = error or seguridad.validar_clave(nueva) or (None if nueva == nueva2 else 'Las contraseñas nuevas no coinciden.')
        if error:
            st.error(error)
        else:
            db.actualizar_usuario(usuario['id'], hash=seguridad.hashear(nueva))
            st.success('Contraseña actualizada.')
