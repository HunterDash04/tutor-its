import hashlib
import hmac
import os
import re
import secrets
import string

ITERACIONES = 200_000


def hashear(clave: str) -> str:
    sal = os.urandom(16)
    h = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal, ITERACIONES)
    return f'pbkdf2_sha256${ITERACIONES}${sal.hex()}${h.hex()}'


def verificar(clave: str, guardado: str) -> bool:
    try:
        _, it, sal, h = guardado.split('$')
        calc = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), bytes.fromhex(sal), int(it))
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


def validar_usuario(usuario: str):
    if not re.fullmatch(r'[a-zA-Z0-9_.]{3,30}', usuario or ''):
        return 'El usuario debe tener entre 3 y 30 caracteres: letras, números, punto o guion bajo.'
    return None


def validar_clave(clave: str):
    if len(clave or '') < 8:
        return 'La contraseña debe tener al menos 8 caracteres.'
    return None


def clave_temporal(largo=10):
    """Contraseña aleatoria para que el docente restablezca la cuenta de un estudiante."""
    alfabeto = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alfabeto) for _ in range(largo))
