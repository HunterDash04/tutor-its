import os
import time

from sqlalchemy import (Column, Float, ForeignKey, Integer, MetaData, String, Table, Text,
                        create_engine, insert, select, update)

metadata = MetaData()

usuarios = Table(
    'usuarios', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('usuario', String(60), unique=True, nullable=False),
    Column('nombre', String(120)),
    Column('hash', String(200), nullable=False),
    Column('rol', String(20), nullable=False, default='estudiante'),
    Column('gpa', Float),
    Column('habilidad_inicial', Float),
    Column('handle_cf', String(60)),
    Column('creado_en', Integer),
    Column('ultimo_acceso', Integer),
)

intentos = Table(
    'intentos', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('usuario_id', Integer, ForeignKey('usuarios.id'), nullable=False, index=True),
    Column('id_problema', String(20), nullable=False),
    Column('nombre_problema', String(200)),
    Column('rating', Float),
    Column('etiquetas', Text),
    Column('categoria_objetivo', String(60)),
    Column('estado_previo', String(80)),
    Column('p_exito', Float),
    Column('meta', Float),
    Column('mostrado_en', Integer, nullable=False),
    Column('registrado_en', Integer),
    Column('resultado', String(20)),          # resuelto | no_resuelto | omitido
    Column('envios', Integer),
    Column('tiempo_s', Integer),
    Column('modo', String(20)),               # manual | codeforces
    Column('estado_resultante', String(80)),
    Column('habilidad_despues', Float),
)


consentimientos = Table(
    'consentimientos', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('usuario_id', Integer, ForeignKey('usuarios.id'), nullable=False, index=True),
    Column('version_aviso', String(20), nullable=False),
    Column('aceptado_en', Integer, nullable=False),
)

# Intentos fallidos de inicio de sesión por nombre de usuario (también para nombres inexistentes,
# para no revelar qué cuentas existen). Es una tabla nueva: create_all la crea sin modificar las demás.
bloqueos = Table(
    'bloqueos_acceso', metadata,
    Column('usuario', String(60), primary_key=True),
    Column('fallos', Integer, nullable=False, default=0),
    Column('bloqueado_hasta', Integer, nullable=False, default=0),
)


def _url():
    try:
        import streamlit as st
        if 'DATABASE_URL' in st.secrets:
            return st.secrets['DATABASE_URL']
    except Exception:
        pass
    return os.environ.get('DATABASE_URL', 'sqlite:///its_local.db')


_engine = None


def motor_bd():
    global _engine
    if _engine is None:
        url = _url()
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        kwargs = {'pool_pre_ping': True}
        if url.startswith('sqlite'):
            kwargs['connect_args'] = {'check_same_thread': False}
        _engine = create_engine(url, **kwargs)
        metadata.create_all(_engine)
    return _engine


def ahora():
    return int(time.time())


# ---------------- usuarios ----------------
def buscar_usuario(usuario):
    with motor_bd().connect() as c:
        r = c.execute(select(usuarios).where(usuarios.c.usuario == usuario.strip().lower())).mappings().first()
        return dict(r) if r else None


def usuario_por_id(uid):
    with motor_bd().connect() as c:
        r = c.execute(select(usuarios).where(usuarios.c.id == uid)).mappings().first()
        return dict(r) if r else None


def crear_usuario(usuario, hash_, nombre='', rol='estudiante'):
    with motor_bd().begin() as c:
        r = c.execute(insert(usuarios).values(usuario=usuario.strip().lower(), hash=hash_, nombre=nombre,
                                              rol=rol, creado_en=ahora(), ultimo_acceso=ahora()))
        return r.inserted_primary_key[0]


def actualizar_usuario(uid, **campos):
    with motor_bd().begin() as c:
        c.execute(update(usuarios).where(usuarios.c.id == uid).values(**campos))


def listar_estudiantes():
    with motor_bd().connect() as c:
        return [dict(r) for r in c.execute(select(usuarios).where(usuarios.c.rol == 'estudiante')
                                           .order_by(usuarios.c.creado_en)).mappings()]


# ---------------- intentos ----------------
def intentos_de(uid):
    with motor_bd().connect() as c:
        return [dict(r) for r in c.execute(select(intentos).where(intentos.c.usuario_id == uid)
                                           .order_by(intentos.c.mostrado_en, intentos.c.id)).mappings()]


def crear_intento(**valores):
    with motor_bd().begin() as c:
        return c.execute(insert(intentos).values(**valores)).inserted_primary_key[0]


def actualizar_intento(iid, **campos):
    with motor_bd().begin() as c:
        c.execute(update(intentos).where(intentos.c.id == iid).values(**campos))


def todos_los_intentos():
    with motor_bd().connect() as c:
        return [dict(r) for r in c.execute(select(intentos)).mappings()]


# ---------------- consentimiento de tratamiento de datos ----------------
def registrar_consentimiento(uid, version):
    with motor_bd().begin() as c:
        c.execute(insert(consentimientos).values(usuario_id=uid, version_aviso=version, aceptado_en=ahora()))


# ---------------- control de intentos de inicio de sesión ----------------
def _clave_bloqueo(usuario):
    return (usuario or '').strip().lower()[:60]


def segundos_bloqueo(usuario):
    """Segundos que faltan para desbloquear la cuenta (0 si no está bloqueada)."""
    with motor_bd().connect() as c:
        r = c.execute(select(bloqueos).where(bloqueos.c.usuario == _clave_bloqueo(usuario))).mappings().first()
    return max(0, r['bloqueado_hasta'] - ahora()) if r else 0


def registrar_fallo(usuario, max_intentos, minutos):
    """Suma un intento fallido; al llegar al máximo bloquea la cuenta. Devuelve los intentos restantes."""
    clave = _clave_bloqueo(usuario)
    with motor_bd().begin() as c:
        r = c.execute(select(bloqueos).where(bloqueos.c.usuario == clave)).mappings().first()
        fallos = (r['fallos'] if r else 0) + 1
        hasta = ahora() + minutos * 60 if fallos >= max_intentos else 0
        if fallos >= max_intentos:
            fallos = 0
        if r:
            c.execute(update(bloqueos).where(bloqueos.c.usuario == clave).values(fallos=fallos, bloqueado_hasta=hasta))
        else:
            c.execute(insert(bloqueos).values(usuario=clave, fallos=fallos, bloqueado_hasta=hasta))
    return 0 if hasta else max_intentos - fallos


def limpiar_fallos(usuario):
    with motor_bd().begin() as c:
        c.execute(update(bloqueos).where(bloqueos.c.usuario == _clave_bloqueo(usuario)).values(fallos=0, bloqueado_hasta=0))
