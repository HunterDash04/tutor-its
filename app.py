import streamlit as st

from its_web import db, seguridad, servicio, vistas_docente, vistas_estudiante
from its_web.privacidad import TEXTO_AVISO, VERSION_AVISO

NOMBRE_APP = 'Tutor Inteligente de Programación'
ICONO_APP = ':material/school:'
ICONO_FAVICON = '🎓'

st.set_page_config(page_title=NOMBRE_APP, page_icon=ICONO_FAVICON, layout='wide')

# Oculta los textos de ayuda que Streamlit muestra en inglés
# ("Press Enter to submit form", "Running...", barra de herramientas de las tablas).
st.markdown('''<style>
[data-testid="InputInstructions"] {display: none !important;}
[data-testid="stStatusWidget"] {visibility: hidden;}
[data-testid="stElementToolbar"] {display: none !important;}
</style>''', unsafe_allow_html=True)


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
    # Columna central angosta para que el inicio de sesión no ocupe todo el ancho
    _, centro, _ = st.columns([1, 1.3, 1])
    with centro:
        _formulario_acceso()


def _formulario_acceso():
    st.write('')
    st.markdown(f'## {ICONO_APP} {NOMBRE_APP}', text_alignment='center')
    st.caption('Rutas de práctica personalizadas con problemas reales de Codeforces, '
               'adaptadas a tu nivel después de cada ejercicio.', text_alignment='center')
    entrar, registrarse = st.tabs(['Iniciar sesión', 'Crear cuenta'])
    with entrar:
        with st.form('login'):
            usuario = st.text_input('Usuario')
            clave = st.text_input('Contraseña', type='password')
            ok = st.form_submit_button('Entrar', type='primary', width='stretch')
        if ok:
            _procesar_ingreso(usuario, clave)
    with registrarse:
        with st.expander('Aviso de privacidad y tratamiento de datos personales'):
            st.markdown(TEXTO_AVISO)
        with st.form('registro'):
            usuario = st.text_input('Elige un usuario')
            nombre = st.text_input('Nombre completo')
            clave = st.text_input('Contraseña (mínimo 8 caracteres)', type='password')
            clave2 = st.text_input('Repite la contraseña', type='password')
            acepta = st.checkbox('He leído y acepto el aviso de privacidad y tratamiento de datos personales')
            ok = st.form_submit_button('Crear cuenta', type='primary', width='stretch')
        if ok:
            error = seguridad.validar_usuario(usuario) or seguridad.validar_clave(clave)
            if not error and clave != clave2:
                error = 'Las contraseñas no coinciden.'
            if not error and not acepta:
                error = 'Para crear tu cuenta debes aceptar el aviso de privacidad.'
            if not error and db.buscar_usuario(usuario):
                error = 'Ese usuario ya existe.'
            if error:
                st.error(error)
            else:
                uid = db.crear_usuario(usuario, seguridad.hashear(clave), nombre.strip())
                db.registrar_consentimiento(uid, VERSION_AVISO)
                st.session_state['uid'] = uid
                st.rerun()


def _procesar_ingreso(usuario, clave):
    """Verifica las credenciales con bloqueo tras varios intentos fallidos."""
    espera = db.segundos_bloqueo(usuario)
    if espera:
        st.error(f'Demasiados intentos fallidos. Por seguridad, la cuenta está bloqueada; '
                 f'intenta de nuevo en {-(-espera // 60)} min.')
        return
    u = db.buscar_usuario(usuario)
    if u and seguridad.verificar(clave, u['hash']):
        db.limpiar_fallos(usuario)
        cambios = {'ultimo_acceso': db.ahora()}
        if seguridad.necesita_actualizar(u['hash']):   # cuentas creadas con el cifrado anterior
            cambios['hash'] = seguridad.hashear(clave)
        db.actualizar_usuario(u['id'], **cambios)
        st.session_state['uid'] = u['id']
        st.rerun()
    restantes = db.registrar_fallo(usuario, seguridad.MAX_INTENTOS, seguridad.MINUTOS_BLOQUEO)
    if restantes == 0:
        st.error(f'Usuario o contraseña incorrectos. Se alcanzó el máximo de {seguridad.MAX_INTENTOS} intentos: '
                 f'la cuenta quedó bloqueada por {seguridad.MINUTOS_BLOQUEO} min.')
    else:
        st.error(f'Usuario o contraseña incorrectos. Te quedan {restantes} intento(s).')


def barra_lateral(u):
    with st.sidebar:
        st.markdown(f'### {ICONO_APP} {NOMBRE_APP}')
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
        vistas_docente.estudiantes()
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
