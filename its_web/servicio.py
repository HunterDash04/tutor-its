import numpy as np
import pandas as pd

from motor_recomendacion import EstadoEstudiante, MotorRecomendacion, META_POR_ESTADO
from reglas_diagnostico import diagnosticar_estado_vivo, ESTADO_NORMAL
from topicos_codeforces import CATEGORIAS, categorias_de
from its_web import db

# Calibración inicial de la habilidad (escala de dificultad de Codeforces) según el GPA (0-20)
HABILIDAD_POR_GPA = [(17.0, 1400.0, 'Alto rendimiento'), (13.0, 1150.0, 'Promedio'), (0.0, 900.0, 'Nivelación')]


def habilidad_inicial(gpa):
    return next((h, p) for umbral, h, p in HABILIDAD_POR_GPA if gpa >= umbral)


def cargar_motor(ruta='motor_recomendacion.pkl'):
    return MotorRecomendacion(ruta)


def _exito_primer_envio(it):
    return it['resultado'] == 'resuelto' and (it['envios'] or 1) <= 1


def reconstruir(usuario, historial):
    """Recorre los intentos registrados en orden y devuelve (estado, estado_cognitivo, pendiente)."""
    est = EstadoEstudiante(habilidad_inicial=usuario['habilidad_inicial'] or 1000.0)
    estado_cog = ESTADO_NORMAL
    pendiente = None
    for it in historial:
        est.vistos.add(it['id_problema'])
        if it['registrado_en'] is None:
            pendiente = it
            continue
        if it['resultado'] in ('resuelto', 'no_resuelto'):
            cats = categorias_de(it['etiquetas'])
            est.actualizar(it['rating'], cats, _exito_primer_envio(it), it['id_problema'])
            if it['estado_resultante']:
                estado_cog = it['estado_resultante']
    return est, estado_cog, pendiente


def motivo(estado_cog, categoria, meta):
    if estado_cog.startswith('Riesgo'):
        return (f'Tu último resultado indica que conviene afianzar bases. Se eligió un problema de '
                f'**{categoria}** (tu categoría más débil) con una probabilidad de éxito cercana a {meta:.0%}.')
    if estado_cog.startswith('Dominio'):
        return (f'Vas muy bien: se eligió un reto en **{categoria}**, una categoría que has practicado poco, '
                f'con una probabilidad de éxito cercana a {meta:.0%} para que te exija.')
    return (f'Progreso estable: se eligió un problema de **{categoria}**, tu categoría más débil hasta ahora, '
            f'con una probabilidad de éxito cercana a {meta:.0%}.')


def recomendacion_actual(motor, usuario):
    """Devuelve el intento pendiente (lo crea si no existe)."""
    historial = db.intentos_de(usuario['id'])
    est, estado_cog, pendiente = reconstruir(usuario, historial)
    if pendiente:
        return pendiente
    prob, cat, meta = motor.recomendar(est, estado_cog, rng=np.random.default_rng())
    iid = db.crear_intento(
        usuario_id=usuario['id'], id_problema=prob['id_problema'], nombre_problema=prob['nombre'],
        rating=float(prob['rating']), etiquetas=prob['etiquetas'], categoria_objetivo=cat,
        estado_previo=estado_cog, p_exito=float(prob['p_exito']), meta=float(meta), mostrado_en=db.ahora())
    return next(i for i in db.intentos_de(usuario['id']) if i['id'] == iid)


def registrar(usuario, intento, resultado, envios, modo, tiempo_s=None):
    """resultado: 'resuelto' | 'no_resuelto' | 'omitido'. Devuelve el diagnóstico obtenido."""
    if tiempo_s is None:
        tiempo_s = max(0, db.ahora() - intento['mostrado_en'])
    diag = None
    if resultado != 'omitido':
        diag = diagnosticar_estado_vivo(tiempo_s, max(int(envios), 1), 1 if resultado == 'resuelto' else 0, dias_atraso=0)
    db.actualizar_intento(intento['id'], registrado_en=db.ahora(), resultado=resultado,
                          envios=int(envios) if envios is not None else None, tiempo_s=int(tiempo_s),
                          modo=modo, estado_resultante=diag)
    est, _, _ = reconstruir(usuario, db.intentos_de(usuario['id']))
    db.actualizar_intento(intento['id'], habilidad_despues=float(est.habilidad))
    return diag


def resumen(usuario, historial=None):
    """Datos para los paneles de progreso."""
    historial = historial if historial is not None else db.intentos_de(usuario['id'])
    est, estado_cog, _ = reconstruir(usuario, historial)
    hechos = [h for h in historial if h['resultado'] in ('resuelto', 'no_resuelto')]
    dom = est.dominio_por_categoria()
    practicas = {c: est.exitos_cat[c] + est.fallos_cat[c] for c in CATEGORIAS}
    df_dom = pd.DataFrame({'Categoría': CATEGORIAS,
                           'Dominio estimado': [dom[c] for c in CATEGORIAS],
                           'Problemas': [practicas[c] for c in CATEGORIAS]})
    practicadas = df_dom[df_dom['Problemas'] > 0]
    return {
        'estado': est, 'estado_cognitivo': estado_cog, 'habilidad': est.habilidad,
        'n_hechos': len(hechos),
        'n_resueltos': sum(h['resultado'] == 'resuelto' for h in hechos),
        'n_primer_envio': sum(_exito_primer_envio(h) for h in hechos),
        'dominio': df_dom,
        'mas_debil': practicadas.sort_values('Dominio estimado').iloc[0]['Categoría'] if len(practicadas) else None,
        'historial': historial,
    }
