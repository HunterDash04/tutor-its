"""
descargar_codeforces.py — descarga datos REALES de Codeforces para el recomendador.

Usa solo la API pública oficial (https://codeforces.com/apiHelp), sin clave.
Respeta el límite de ~1 consulta cada 2 segundos.

Qué descarga:
  1. Catálogo de problemas con sus etiquetas reales y su dificultad (rating).
  2. Una muestra aleatoria de usuarios ACTIVOS de nivel principiante-intermedio
     (rating 800-1599), para que se parezcan a estudiantes que están aprendiendo.
  3. El historial de envíos de cada usuario de la muestra (veredicto, hora, problema).

Privacidad: los nombres de usuario se reemplazan por un identificador anónimo
(hash); en los CSV no queda ningún handle.

Uso (desde la raíz del repositorio):
    py pipeline/descargar_codeforces.py            -> 1500 usuarios (aprox. 1 hora)
    py pipeline/descargar_codeforces.py 300        -> prueba rápida con 300 usuarios
Si se corta, vuelve a ejecutarlo: continúa donde se quedó.

Genera en datasets/codeforces/:
    problemas_codeforces.csv   (id_problema, nombre, rating, etiquetas)
    envios_codeforces.csv      (id_usuario, rating_usuario, id_problema, veredicto, tiempo_unix, ...)
"""
import csv
import hashlib
import json
import os
import random
import sys
import time
import urllib.request
import urllib.error

API = 'https://codeforces.com/api/'
CARPETA = os.path.join('datasets', 'codeforces')
RUTA_PROBLEMAS = os.path.join(CARPETA, 'problemas_codeforces.csv')
RUTA_ENVIOS = os.path.join(CARPETA, 'envios_codeforces.csv')
RUTA_MUESTRA = os.path.join(CARPETA, '_muestra_usuarios.json')
RUTA_HECHOS = os.path.join(CARPETA, '_usuarios_descargados.txt')

RATING_MIN, RATING_MAX = 800, 1599
ENVIOS_POR_USUARIO = 1000
PAUSA = 2.1
SEMILLA = 42
SAL = 'tesis-its-unmsm'  # sal fija para que el hash sea reproducible

_ultima = [0.0]


def llamar(metodo, reintentos=5):
    url = API + metodo
    for intento in range(reintentos):
        espera = PAUSA - (time.time() - _ultima[0])
        if espera > 0:
            time.sleep(espera)
        _ultima[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'tesis-its-unmsm/1.0'})
            with urllib.request.urlopen(req, timeout=60) as r:
                datos = json.loads(r.read().decode('utf-8'))
            if datos.get('status') == 'OK':
                return datos['result']
            comentario = datos.get('comment', '')
            if 'not found' in comentario.lower():
                return None
            print(f'   API respondió FAILED: {comentario}')
        except urllib.error.HTTPError as e:
            if e.code == 400:
                return None
            print(f'   HTTP {e.code}, reintento {intento + 1}/{reintentos}')
        except Exception as e:
            print(f'   Error de red ({e}), reintento {intento + 1}/{reintentos}')
        time.sleep(5 * (intento + 1))
    return None


def anonimo(handle):
    return 'u_' + hashlib.sha256((SAL + handle.lower()).encode()).hexdigest()[:12]


def descargar_problemas():
    if os.path.exists(RUTA_PROBLEMAS):
        print('[1/3] Catálogo ya descargado.')
        return
    print('[1/3] Descargando catálogo de problemas...')
    res = llamar('problemset.problems')
    if res is None:
        sys.exit('No se pudo descargar el catálogo. Revisa tu conexión y vuelve a intentar.')
    resueltos = {(s['contestId'], s['index']): s.get('solvedCount', 0)
                 for s in res.get('problemStatistics', [])}
    with open(RUTA_PROBLEMAS, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['id_problema', 'contest_id', 'indice', 'nombre', 'rating', 'etiquetas', 'veces_resuelto'])
        for p in res['problems']:
            if 'contestId' not in p:
                continue
            w.writerow([f"{p['contestId']}{p['index']}", p['contestId'], p['index'], p['name'],
                        p.get('rating', ''), ';'.join(p.get('tags', [])),
                        resueltos.get((p['contestId'], p['index']), 0)])
    print(f"   {len(res['problems']):,} problemas guardados.")


def elegir_muestra(n):
    if os.path.exists(RUTA_MUESTRA):
        with open(RUTA_MUESTRA, encoding='utf-8') as f:
            muestra = json.load(f)
        print(f'[2/3] Muestra existente: {len(muestra)} usuarios.')
        return muestra
    print('[2/3] Descargando lista de usuarios activos (archivo grande, puede tardar 1-2 min)...')
    res = llamar('user.ratedList?activeOnly=true&includeRetired=false')
    if res is None:
        sys.exit('No se pudo descargar la lista de usuarios.')
    candidatos = [{'handle': u['handle'], 'rating': u.get('rating', 0)}
                  for u in res if RATING_MIN <= u.get('rating', 0) <= RATING_MAX]
    random.Random(SEMILLA).shuffle(candidatos)
    muestra = candidatos[:n]
    with open(RUTA_MUESTRA, 'w', encoding='utf-8') as f:
        json.dump(muestra, f)
    print(f'   {len(candidatos):,} usuarios en el rango {RATING_MIN}-{RATING_MAX}; se eligen {len(muestra)} al azar.')
    return muestra


def descargar_envios(muestra):
    hechos = set()
    if os.path.exists(RUTA_HECHOS):
        with open(RUTA_HECHOS, encoding='utf-8') as f:
            hechos = {l.strip() for l in f if l.strip()}
    nuevo = not os.path.exists(RUTA_ENVIOS)
    pendientes = [u for u in muestra if anonimo(u['handle']) not in hechos]
    print(f'[3/3] Descargando envíos: {len(pendientes)} usuarios pendientes '
          f'(~{len(pendientes) * PAUSA / 60:.0f} min).')
    with open(RUTA_ENVIOS, 'a', newline='', encoding='utf-8') as fe, \
            open(RUTA_HECHOS, 'a', encoding='utf-8') as fh:
        w = csv.writer(fe)
        if nuevo:
            w.writerow(['id_usuario', 'rating_usuario', 'id_envio', 'id_problema', 'rating_problema',
                        'etiquetas', 'veredicto', 'tests_superados', 'tiempo_unix', 'lenguaje',
                        'tipo_participante'])
        for k, u in enumerate(pendientes, 1):
            uid = anonimo(u['handle'])
            res = llamar(f"user.status?handle={u['handle']}&from=1&count={ENVIOS_POR_USUARIO}")
            for s in res or []:
                p = s.get('problem', {})
                if 'contestId' not in p:
                    continue
                w.writerow([uid, u['rating'], s.get('id'), f"{p['contestId']}{p['index']}",
                            p.get('rating', ''), ';'.join(p.get('tags', [])), s.get('verdict', ''),
                            s.get('passedTestCount', ''), s.get('creationTimeSeconds', ''),
                            s.get('programmingLanguage', ''),
                            s.get('author', {}).get('participantType', '')])
            fh.write(uid + '\n')
            fe.flush(); fh.flush()
            if k % 25 == 0 or k == len(pendientes):
                print(f'   {k}/{len(pendientes)} usuarios')


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    os.makedirs(CARPETA, exist_ok=True)
    descargar_problemas()
    muestra = elegir_muestra(n)
    descargar_envios(muestra)
    print(f'\nListo. Archivos en {CARPETA}/')


if __name__ == '__main__':
    main()
