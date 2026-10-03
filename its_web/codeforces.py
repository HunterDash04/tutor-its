import json
import urllib.parse
import urllib.request

API = 'https://codeforces.com/api/'
IGNORADOS = {'COMPILATION_ERROR', 'SKIPPED', 'TESTING', 'REJECTED'}

VEREDICTOS = {
    'OK': 'Aceptado',
    'WRONG_ANSWER': 'Respuesta incorrecta',
    'TIME_LIMIT_EXCEEDED': 'Tiempo límite excedido',
    'MEMORY_LIMIT_EXCEEDED': 'Memoria excedida',
    'RUNTIME_ERROR': 'Error en tiempo de ejecución',
    'IDLENESS_LIMIT_EXCEEDED': 'Límite de inactividad excedido',
    'PRESENTATION_ERROR': 'Error de formato de salida',
    'CHALLENGED': 'Solución hackeada',
    'PARTIAL': 'Parcialmente correcto',
    'FAILED': 'Fallido',
    'SECURITY_VIOLATED': 'Violación de seguridad',
    'CRASHED': 'Error del juez',
    'INPUT_PREPARATION_CRASHED': 'Error del juez',
}


def _traducir_error(comentario):
    c = (comentario or '').lower()
    if 'not found' in c:
        return 'Ese usuario no existe en Codeforces.'
    if 'limit' in c:
        return 'Codeforces recibió demasiadas consultas. Espera unos segundos e intenta de nuevo.'
    return 'Codeforces no pudo procesar la consulta. Intenta de nuevo en un momento.'


class ErrorCodeforces(Exception):
    pass


def _llamar(metodo, **params):
    url = API + metodo + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'its-programacion/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            datos = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            datos = json.loads(e.read().decode('utf-8'))
        except Exception:
            raise ErrorCodeforces('Codeforces no está disponible en este momento. Intenta más tarde.')
    except Exception:
        raise ErrorCodeforces('No se pudo conectar con Codeforces. Intenta de nuevo en un momento.')
    if datos.get('status') != 'OK':
        raise ErrorCodeforces(_traducir_error(datos.get('comment', '')))
    return datos['result']


def validar_handle(handle):
    """Devuelve el handle con mayúsculas correctas si existe; lanza ErrorCodeforces si no."""
    res = _llamar('user.info', handles=handle.strip())
    return res[0]['handle']


def _id(p):
    return f"{p.get('contestId')}{p.get('index')}"


def verificar_envios(handle, id_problema, desde_unix):
    """Busca los envíos del estudiante a ese problema desde que se le recomendó.

    Devuelve dict: encontrado, resuelto, envios, tiempo_s, ultimo_veredicto
    """
    envios = _llamar('user.status', handle=handle, **{'from': 1, 'count': 200})
    propios = [s for s in envios
               if _id(s.get('problem', {})) == id_problema
               and s.get('creationTimeSeconds', 0) >= desde_unix - 60
               and s.get('verdict') not in IGNORADOS]
    propios.sort(key=lambda s: s['creationTimeSeconds'])
    if not propios:
        return {'encontrado': False}
    for i, s in enumerate(propios, 1):
        if s.get('verdict') == 'OK':
            return {'encontrado': True, 'resuelto': True, 'envios': i,
                    'tiempo_s': max(0, s['creationTimeSeconds'] - desde_unix), 'ultimo_veredicto': 'Aceptado'}
    return {'encontrado': True, 'resuelto': False, 'envios': len(propios),
            'tiempo_s': max(0, propios[-1]['creationTimeSeconds'] - desde_unix),
            'ultimo_veredicto': VEREDICTOS.get(propios[-1].get('verdict', ''), propios[-1].get('verdict', ''))}
