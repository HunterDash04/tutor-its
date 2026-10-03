"""
Aplicación web del sistema de recomendación de rutas de aprendizaje en programación.

Ejecutar en local:   streamlit run app.py
Base de datos: usa DATABASE_URL (secretos de Streamlit) si existe; si no, SQLite local.
"""
import streamlit as st

from its_web import db, seguridad, servicio, vistas_docente, vistas_estudiante

NOMBRE_APP = 'Tutor Inteligente de Programación'

st.set_page_config(page_title=NOMBRE_APP, page_icon='🧭', layout='wide')


@st.cache_resource(show_spinner='Cargando el modelo de recomendación...')
def motor():
    return servicio.cargar_motor('motor_recomendacion.pkl')


@st.cache_resource
def asegurar_docente():
    """Si los secretos definen [docente], crea esa cuenta la primera vez (no cambia una existente)."""
    try:
        conf = st.secrets.get('docente')
    except Exception:
        conf = None
    if conf and conf.get('usuario') and conf.get('clave') and not db.buscar_usuario(conf['usuario']):
        db.crear_usuario(conf['usuario'], seguridad.hashear(conf['clave']), conf.get('nombre', 'Docente'), rol='docente')
    return True


def acceso():
    st.title(f'🧭 {NOMBRE_APP}')
    st.caption('Rutas de práctica personalizadas con problemas reales de Codeforces, '
               'adaptadas a tu nivel después de cada ejercicio.')
    entrar, registrarse = st.tabs(['Iniciar sesión', 'Crear cuenta'])
    with entrar:
        with st.form('login'):
            usuario = st.text_input('Usuario')
            clave = st.text_input('Contraseña', type='password')
            ok = st.form_submit_button('Entrar', type='primary')
        if ok:
            u = db.buscar_usuario(usuario)
            if u and seguridad.verificar(clave, u['hash']):
                db.actualizar_usuario(u['id'], ultimo_acceso=db.ahora())
                st.session_state['uid'] = u['id']
                st.rerun()
            else:
                st.error('Usuario o contraseña incorrectos.')
    with registrarse:
        with st.form('registro'):
            usuario = st.text_input('Elige un usuario')
            nombre = st.text_input('Nombre completo')
            clave = st.text_input('Contraseña (mínimo 8 caracteres)', type='password')
            clave2 = st.text_input('Repite la contraseña', type='password')
            ok = st.form_submit_button('Crear cuenta', type='primary')
        if ok:
            error = seguridad.validar_usuario(usuario) or seguridad.validar_clave(clave)
            if not error and clave != clave2:
                error = 'Las contraseñas no coinciden.'
            if not error and db.buscar_usuario(usuario):
                error = 'Ese usuario ya existe.'
            if error:
                st.error(error)
            else:
                st.session_state['uid'] = db.crear_usuario(usuario, seguridad.hashear(clave), nombre.strip())
                st.rerun()


def barra_lateral(u):
    with st.sidebar:
        st.markdown(f'### 🧭 {NOMBRE_APP}')
        st.write(f"**{u['nombre'] or u['usuario']}**")
        st.caption('Docente' if u['rol'] == 'docente' else 'Estudiante')
        if st.button('Cerrar sesión', width='stretch'):
            st.session_state.clear()
            st.rerun()


def main():
    asegurar_docente()
    uid = st.session_state.get('uid')
    u = db.usuario_por_id(uid) if uid else None
    if not u:
        acceso()
        return
    barra_lateral(u)
    if u['rol'] == 'docente':
        st.title('Panel docente')
        t1, t2 = st.tabs(['Estudiantes', 'Métricas de los modelos'])
        with t1:
            vistas_docente.estudiantes()
        with t2:
            vistas_docente.metricas()
        return
    if u['habilidad_inicial'] is None:
        vistas_estudiante.bienvenida(u)
        return
    t1, t2, t3 = st.tabs(['Practicar', 'Mi progreso', 'Mi cuenta'])
    with t1:
        vistas_estudiante.practicar(motor(), u)
    with t2:
        vistas_estudiante.progreso(u)
    with t3:
        vistas_estudiante.cuenta(u)


main()
