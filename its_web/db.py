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
